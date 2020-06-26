from CTFd.models import db


class Containers(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner = db.Column(db.Integer)
    name = db.Column(db.String(80))
    buildfile = db.Column(db.Text)

    def __init__(self, owner, name, buildfile):
        self.owner = owner
        self.name = name
        self.buildfile = buildfile

    def __repr__(self):
        return "<Container ID:(0) {1}>".format(self.id, self.name)