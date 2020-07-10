from flask import current_app as app, render_template, request, redirect, jsonify, url_for, Blueprint, session
from CTFd.models import db
from .models import Containers
from CTFd.utils.decorators import (
    during_ctf_time_only,
    authed_only,
    admins_only,
    cache
)
from . import utils
import math

def load(app):
    app.db.create_all()
    containers = Blueprint('containers', __name__, template_folder='templates')

    @containers.route('/containers', methods=['GET'])
    @during_ctf_time_only
    @authed_only
    def list_container():
        containers_per_page = 10
        # Get page if page parameter is set in the url
        page = 1
        if 'page' in request.args:
            page = int(request.args.get('page'))
        
        # Get amount of items
        count = Containers.query.filter(Containers.owner==session["id"]).filter(Containers.deleted == False).count()

        # Get all containers that the user owns and that are not deleted by the user
        containers = Containers.query.filter(Containers.owner==session["id"]).filter(Containers.deleted == False).paginate(page=page, per_page=containers_per_page).items

        for c in containers:
            # We get the container stauts by using the docker inspect command
            c.status = utils.container_status(c.name)
            # Ports are also from inspect
            c.ports = ', '.join(utils.container_ports(c.name, verbose=True))
        # We render the container page with all the users containers
        return render_template('containers.html', containers=containers, pages=math.ceil(count/containers_per_page), page=page, admin=False, base="base.html")


    @containers.route('/containers/<int:container_id>/stop', methods=['POST'])
    @during_ctf_time_only
    @authed_only
    def stop_container(container_id):
        container = Containers.query.filter_by(id=container_id).first_or_404()
        # Check if the user actually owns the container
        if container.owner is not session["id"]:
            return '0'
        if utils.container_stop(container.name):
            return '1'
        else:
            return '0'


    @containers.route('/containers/<int:container_id>/start', methods=['POST'])
    @during_ctf_time_only
    @authed_only
    def run_container(container_id):
        container = Containers.query.filter_by(id=container_id).first_or_404()
        # Check if the user actually owns the container
        if container.owner is not session["id"]:
            return '0'
        # Check if the container still exists, if not we use the image
        if utils.container_status(container.name) == 'missing':
            if utils.run_image(container.name):
                return '1'
            else:
                return '0'
        else:
            if utils.container_start(container.name):
                return '1'
            else:
                return '0'


    @containers.route('/containers/<int:container_id>/delete', methods=['POST'])
    @during_ctf_time_only
    @authed_only
    def delete_container(container_id):
        container = Containers.query.filter_by(id=container_id).first_or_404()
        # Check if the user actually owns the container
        if container.owner is not session["id"]:
            return '0'
        if utils.delete_image(container.name):
            # We don't delete the container info from the db because we want to log them
            container.deleted = True
            db.session.commit()
            db.session.close()
        return '1'


    @containers.route('/containers/new', methods=['POST'])
    @during_ctf_time_only
    @authed_only
    def new_container():
        # We append the username so that the user can only access containers in their own namespace
        name = session["name"] + "-" + request.form.get('name')
        # Docker requires lowercase lettering
        name = name.lower()
        # If another container has the same name, add a random string to it
        if utils.container_already_exists(name):
            name += '_' + utils.randomString(8)
        # Check that the name is valid
        if not set(name) <= set('abcdefghijklmnopqrstuvwxyz0123456789-_'):
            return redirect(url_for('containers.list_container'))
        owner = session["id"]
        buildfile = request.form.get('buildfile')
        # Files are the associated files you can upload
        files = request.files.getlist('files[]')
        utils.create_image(owner=owner, name=name, buildfile=buildfile, files=files)
        utils.run_image(name)
        return redirect(url_for('containers.list_container'))


    @containers.route('/containers/import', methods=['POST'])
    @during_ctf_time_only
    @authed_only
    def import_container():
        # Appending the namespace
        name = session["name"] + "-" + request.form.get('name')
        # Check that the name is valid
        if not set(name) <= set('abcdefghijklmnopqrstuvwxyz0123456789-_'):
            return redirect(url_for('containers.list_container'))
        utils.import_image(name=name)
        return redirect(url_for('containers.list_container'))
    
    @containers.route('/admin/containers/overview', methods=['GET'])
    @admins_only
    def admin_overview():
        containers_per_page = 10
        # Get page if page parameter is set in the url
        page = 1
        if 'page' in request.args:
            page = int(request.args.get('page'))
        
        # Get page if page parameter is set in the url
        running = False
        if 'running' in request.args:
            if request.args.get('running') == 'True':
                running = True

        # The admin can view all past and present containers
        # Get amount of items
        all_containers = Containers.query
        # Check if the admin wants to display only running containers
        if running:
            for c in all_containers:
                if utils.container_status(c.name) == 'running':
                    c.running = True
            all_containers = all_containers.filter_by(running=True)

        # Get amount of containers and divide them into pages
        count = all_containers.count()
        containers = all_containers.paginate(page=page, per_page=containers_per_page).items
        # Add info about the containers from docker inspect
        for c in containers:
            c.status = utils.container_status(c.name)
            c.ports = ', '.join(utils.container_ports(c.name, verbose=True))

        return render_template('containers.html', containers=containers, pages=math.ceil(count/containers_per_page), page=page, running=running, admin=True, base="admin/base.html")
    
    @containers.route('/admin/containers/<int:container_id>', methods=['GET'])
    @admins_only
    def get_dockerfile(container_id):
        # The admin can view the buildfile of all containers
        container = Containers.query.filter_by(id=container_id).first_or_404()
        # <pre> tags are so that the newlines are interperated
        return "<pre>" + container.buildfile + "</pre>"

    @containers.route('/admin/conatainers/delete_all_deleted', methods=['POST'])
    @admins_only
    def delete_all():
        # The admin can view the buildfile of all containers
        try:
            rows_deleted_count = Containers.query.filter_by(deleted=True).delete()
            db.session.commit()
            return '1'
        except:
            db.session.rollback()
            return '0'

    app.register_blueprint(containers)