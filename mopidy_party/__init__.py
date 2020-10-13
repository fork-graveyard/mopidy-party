import os

import pykka
import tornado.web

from mopidy import core, config, ext

__version__ = '1.0.0'


class PartyRequestHandler(tornado.web.RequestHandler):

    def initialize(self, core, data, config):
        self.core = core
        self.data = data
        self.requiredVotes = config["party"]["votes_to_skip"]

    def get(self):
        currentTrack = self.core.playback.get_current_track().get()
        if (currentTrack == None): return
        currentTrackURI = currentTrack.uri

        # If the current track is different to the one stored, clear votes
        if (currentTrackURI != self.data["track"]):
            self.data["track"] = currentTrackURI
            self.data["votes"] = []

        if (self.request.remote_ip in self.data["votes"]): # User has already voted
            self.write("You have already voted to skip this song =)")
        else: # Valid vote
            self.data["votes"].append(self.request.remote_ip)
            if (len(self.data["votes"]) == self.requiredVotes):
                self.core.playback.next()
                self.write("Skipping...")
            else:
                self.write("You have voted to skip this song. ("+str(self.requiredVotes-len(self.data["votes"]))+" more votes needed)")

class PartyFrontend(pykka.ThreadingActor, core.CoreListener):
    def __init__(self, config, core):
        super().__init__()
        self.core = core
        self.index = 0
        if config["party"]["fallback_playlist"] != "-":
            self.playlist = self.core.playlists.lookup(config["party"]["fallback_playlist"]).get()
        else:
            self.playlist = None
            # logger.info("no fallback playlist selected; available are", [dict(name=p.name, uri=p.uri) for p in self.core.playlists.as_list().get()])

    def playback_state_changed(self, old_state, new_state):
        if new_state == "stopped" and self.playlist: # ran out of items to play
            self.core.tracklist.add([self.playlist.tracks[self.index]])
            self.index = (self.index + 1) % self.playlist.length
            self.core.playback.play()

def party_factory(config, core):
    data = {'track':"", 'votes':[]}
    return [
    ('/vote', PartyRequestHandler, {'core': core, 'data':data, 'config':config})
    ]


class Extension(ext.Extension):

    dist_name = 'Mopidy-Party'
    ext_name = 'party'
    version = __version__

    def get_default_config(self):
        conf_file = os.path.join(os.path.dirname(__file__), 'ext.conf')
        return config.read(conf_file)

    def get_config_schema(self):
        schema = super(Extension, self).get_config_schema()
        schema['votes_to_skip'] = config.Integer(minimum=0)
        schema['fallback_playlist'] = config.String(optional=True)
        return schema

    def setup(self, registry):
        registry.add('http:static', {
            'name': self.ext_name,
            'path': os.path.join(os.path.dirname(__file__), 'static'),
        })
        registry.add('http:app', {
            'name': self.ext_name,
            'factory': party_factory,
        })
        registry.add('frontend', PartyFrontend)
