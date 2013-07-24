import xmlrpclib

from ..exceptions import PyCallGraphException
from .output import Output


class UbigraphOutput(Output):
    def __init__(self):
        self.fp = None
        self.server_url = 'http://127.0.0.1:20738/RPC2'

    def start(self):
        server = xmlrpclib.Server(self.server_url)
        self.graph = server.ubigraph

        # Create a graph
        for i in range(0,10):
            self.graph.new_vertex_w_id(i)

        # Make some edges
        for i in range(0,10):
            self.graph.new_edge(i, (i+1)%10)

    def should_update(self):
        return True

    def update(self):
        pass

    @classmethod
    def add_arguments(cls, subparsers):
        defaults = cls()

        subparser = subparsers.add_parser('ubigraph',
            help='Update an Ubigraph visualisation in real time')

        subparser.add_argument('-s', '--server-url', type=str,
            default=defaults.server_url,
            help='The Ubigraph server')

    def done(self):
        pass
