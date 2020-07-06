from CTFd.models import db


class Containers(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner = db.Column(db.Integer)
    name = db.Column(db.String(80))
    buildfile = db.Column(db.Text)
    running = db.Column(db.Boolean)
    deleted = db.Column(db.Boolean)

    def __init__(self, owner, name, buildfile, running, deleted):
        self.owner = owner
        self.name = name
        self.buildfile = buildfile
        self.running = running
        self.deleted = deleted

    def __repr__(self):
        return "<Container ID:(0) {1}>".format(self.id, self.name)