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

def load(app):
    app.db.create_all()
    containers = Blueprint('containers', __name__, template_folder='templates')

    @containers.route('/containers', methods=['GET'])
    @during_ctf_time_only
    @authed_only
    def list_container():
        containers = Containers.query.filter(Containers.owner==session["id"]).all()
        for c in containers:
            c.status = utils.container_status(c.name)
            c.ports = ', '.join(utils.container_ports(c.name, verbose=True))
        return render_template('containers.html', containers=containers)


    @containers.route('/containers/<int:container_id>/stop', methods=['POST'])
    @during_ctf_time_only
    @authed_only
    def stop_container(container_id):
        container = Containers.query.filter_by(id=container_id).first_or_404()
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
        if container.owner is not session["id"]:
            return '0'
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
        if container.owner is not session["id"]:
            return '0'
        if utils.delete_image(container.name):
            container.deleted = True
            db.session.commit()
            db.session.close()
        return '1'


    @containers.route('/containers/new', methods=['POST'])
    @during_ctf_time_only
    @authed_only
    def new_container():
        name = session["name"] + "-" + request.form.get('name')
        name = name.lower()
        if not set(name) <= set('abcdefghijklmnopqrstuvwxyz0123456789-_'):
            return redirect(url_for('containers.list_container'))
        owner = session["id"]
        buildfile = request.form.get('buildfile')
        files = request.files.getlist('files[]')
        utils.create_image(owner=owner, name=name, buildfile=buildfile, files=files)
        utils.run_image(name)
        return redirect(url_for('containers.list_container'))


    @containers.route('/containers/import', methods=['POST'])
    @during_ctf_time_only
    @authed_only
    def import_container():
        name = session["name"] + "-" + request.form.get('name')
        if not set(name) <= set('abcdefghijklmnopqrstuvwxyz0123456789-_'):
            return redirect(url_for('containers.list_container'))
        utils.import_image(name=name)
        return redirect(url_for('containers.list_container'))
    
    @containers.route('/containers/overview', methods=['POST'])
    @admins_only
    def admin_overview():
        containers = Containers.query.all()
        for c in containers:
            c.status = utils.container_status(c.name)
            c.ports = ', '.join(utils.container_ports(c.name, verbose=True))
        return render_template('overview.html', containers=containers)

    app.register_blueprint(containers)