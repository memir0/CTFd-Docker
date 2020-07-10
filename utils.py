from flask import session
from CTFd.utils.decorators import admins_only, is_admin, cache
from CTFd.models import db
from .models import Containers

import json
import os
import subprocess
import socket
import tempfile
import shutil
import re
import random
import string


@cache.memoize()
def can_create_container():
    # Check if docker is installed
    try:
        subprocess.check_output(['docker', 'version'])
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def import_image(name):
    try:
        # If the image exists it is added to the database as a runnable container
        info = json.loads(subprocess.check_output(['docker', 'inspect', '--type=image', name]))
        container = Containers(owner=session["id"], name=name, buildfile=None, deleted=False)
        db.session.add(container)
        db.session.commit()
        db.session.close()
        return True
    except subprocess.CalledProcessError:
        return False


def create_image(owner, name, buildfile, files):
    if not can_create_container():
        return False
    folder = tempfile.mkdtemp(prefix='ctfd')
    tmpfile = tempfile.NamedTemporaryFile(dir=folder, delete=False)
    tmpfile.write(bytes(buildfile, 'utf-8'))
    tmpfile.close()

    # All associated files are adde to our temp foled
    for f in files:
        if f.filename.strip():
            filename = os.path.basename(f.filename)
            f.save(os.path.join(folder, filename))
    # repository name component must match "[a-z0-9](?:-*[a-z0-9])*(?:[._][a-z0-9](?:-*[a-z0-9])*)*"
    # docker build -f tmpfile.name -t name
    try:
        # tmpfile is our docker buildfile
        cmd = ['docker', 'build', '-f', tmpfile.name, '-t', name, folder]
        subprocess.call(cmd)
        container = Containers(owner, name, buildfile, False)
        db.session.add(container)
        db.session.commit()
        db.session.close()
        # Delete the temporary folder
        rmdir(folder)
        return True
    except subprocess.CalledProcessError:
        return False


def is_port_free(port):
    # To check that the port is free we attempt to connect to it
    s = socket.socket()
    result = s.connect_ex(('127.0.0.1', port))
    if result == 0:
        s.close()
        return False
    return True


def delete_image(name):
    try:
        # First we stop the container, then we delete the container and image
        subprocess.call(['docker', 'stop', name])
        subprocess.call(['docker', 'rm', name])
        subprocess.call(['docker', 'rmi', name])
        return True
    except subprocess.CalledProcessError:
        return False


def run_image(name):
    try:
        info = json.loads(subprocess.check_output(['docker', 'inspect', '--type=image', name]))

        try:
            # We attempt to get the ports from the image
            ports_asked = info[0]['Config']['ExposedPorts'].keys()
            ports_asked = [int(re.sub('[A-Za-z/]+', '', port)) for port in ports_asked]
        except KeyError:
            # If there are no ports we get a key error exception
            ports_asked = []

        cmd = ['docker', 'run', '-d']
        ports_used = []
        # Vpn ip is appended to the ports so they are not exposed externally. Requires a ':' at the end. Leave empty to expose externally
        vpn_ip = '10.9.8.1:'
        for port in ports_asked:
            i = 0
            # We attempt 1000 times max to prevent an infinite loop
            while i < 1000:
                # Ports can vary from 10001 to 60000
                arbitrary_port = 10000 + random.randint(1,50000)
                if is_port_free(arbitrary_port):
                    cmd.append('-p')
                    cmd.append(vpn_ip + '{}:{}'.format(arbitrary_port, port))
                    break
                else:
                    i += 1

            # Check if the while loop stopped because of too many failed attempts
            if i >= 1000:
                # If you see this error run the docker prune command
                print("ERROR: Failed to find free port. Clean out unused containers!")
                return False
        cmd += ['--name', name, name]
        subprocess.call(cmd)
        return True
    except subprocess.CalledProcessError:
        return False


def container_start(name):
    try:
        cmd = ['docker', 'start', name]
        subprocess.call(cmd)
        return True
    except subprocess.CalledProcessError:
        return False


def container_stop(name):
    try:
        cmd = ['docker', 'stop', name]
        subprocess.call(cmd)
        return True
    except subprocess.CalledProcessError:
        return False


def container_status(name):
    try:
        # Gets the containers status by inspecting it
        data = json.loads(subprocess.check_output(['docker', 'inspect', '--type=container', name]))
        status = data[0]["State"]["Status"]
        return status
    except subprocess.CalledProcessError:
        return 'missing'



def container_ports(name, verbose=False):
    try:
        info = json.loads(subprocess.check_output(['docker', 'inspect', '--type=container', name]))
        if verbose:
            # We use verbose so that we can se what ports the containers ports are forwarded to
            ports = info[0]["NetworkSettings"]["Ports"]
            if not ports:
                return []
            final = []
            for port in ports.keys():
                final.append("".join([ports[port][0]["HostPort"], '->', port]))
            return final
        else:
            ports = info[0]['Config']['ExposedPorts'].keys()
            if not ports:
                return []
            ports = [int(re.sub('[A-Za-z/]+', '', port)) for port in ports]
            return ports
    except subprocess.CalledProcessError:
        return []

def container_already_exists(name):
    try:
        subprocess.check_output(['docker', 'inspect', '--type=container', name])
        return True
    except subprocess.CalledProcessError:
        # If the inspect fails we assume that the container does not exist
        return False

def randomString(stringLength=28):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))

def rmdir(directory):
    # Deletes specified folder
    shutil.rmtree(directory, ignore_errors=True)