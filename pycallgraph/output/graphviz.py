import tempfile
import os

from ..metadata import __version__
from ..exceptions import PyCallGraphException
from .output import Output


# TODO: Move to base class or a helper image class
def colorize_node(calls, total_time):
    value = float(total_time * 2 + calls) / 3
    return '%f %f %f' % (value / 2 + .5, value, 0.9)


def colorize_edge(calls, total_time):
    value = float(total_time * 2 + calls) / 3
    return '%f %f %f' % (value / 2 + .5, value, 0.7)


class GraphvizSourceOutput(Output):
    def __init__(self):
        self.tool = 'dot'
        self.fp = None
        self.output_file = 'pycallgraph.dot'
        self.font_name = 'Verdana'
        self.font_size = 7
        self.group_font_size = 10
        self.group_border_color = '.5 0 .9'

        self.node_attributes = {
           'color': '%(col)s',
           'label': r'\n'.join([
               '%(func)s',
               'calls: %(hits)i',
               'total time: %(total_time)f',
            ]),
        }

        self.memory_node_label = \
           r'\nmemory in: %(total_memory_in)s' \
           r'\nmemory out: %(total_memory_out)s'

        self.node_color_func = colorize_node
        self.edge_color_func = colorize_edge

        self.time_filter = None

    @classmethod
    def add_arguments(cls, subparsers):
        defaults = cls()

        subparser = subparsers.add_parser('graphviz-source',
            help='Graphviz source generation')

        subparser.add_argument('-o', '--output-file', type=str,
            default=defaults.output_file,
            help='The generated GraphViz dot source')

        cls.add_base_arguments(subparser)

    @classmethod
    def add_base_arguments(cls, subparser):
        defaults = cls()

        subparser.add_argument('--font-name', type=str,
            default=defaults.font_name,
            help='Name of the font to be used')

        subparser.add_argument('--font-size', type=int,
            default=defaults.font_size,
            help='Size of the font to be used')

    def sanity_check(self):
        self.ensure_binary(self.tool)

    def prepare_graph_attributes(self):
        self.graph_attributes = {
            'graph': {
                'overlap': 'scalexy',
                'fontname': self.font_name,
                'fontsize': self.font_size,
                'fontcolor': '0 0 0.5',
                'label':
                    r'Generated by Python Call Graph v%s\n' \
                    r'http://pycallgraph.slowchop.com' % __version__,
            },
            'node': {
                'fontname': self.font_name,
                'fontsize': self.font_size,
                'color': '.5 0 .9',
                'style': 'filled',
                'shape': 'rect',
            },
            'edge': {
                'fontname': self.font_name,
                'fontsize': self.font_size,
                'color': '0 0 0',
            }
        }

        if self.processor.config.track_memory:
            self.node_attributes['label'] += self.memory_node_label

    def done(self):
        self.prepare_output_file()
        self.fp.write(self.generate())

    def generate(self):
        self.prepare_graph_attributes()

        defaults = []
        nodes = []
        edges = []
        groups = []

        # Define default attributes
        for comp, comp_attr in self.graph_attributes.items():
            attr = ', '.join('%s = "%s"' % (attr, val)
                             for attr, val in comp_attr.items() )
            defaults.append('\t%(comp)s [ %(attr)s ];' % locals())

        # XXX: Refactor the following chunks of code so that:
        # - There is a standard way to add attributes to a block
        # - They're extracted into separate methods
        # - Their code visibility is better

        # Define groups
        for group, funcs in self.processor.groups().items():
            funcs = '" "'.join(funcs)
            group_color = self.group_border_color
            group_font_size = self.group_font_size
            groups.append(
                'subgraph cluster_%(group)s { ' \
                '"%(funcs)s"; ' \
                'label = "%(group)s"; ' \
                'node [style=filled]; ' \
                'fontsize = "%(group_font_size)s"; ' \
                'fontcolor = "black"; ' \
                'color="%(group_color)s"; }' % locals())

        # Define nodes
        for func, hits in self.processor.func_count.items():
            # XXX: This line is pretty terrible. Maybe retur an object?
            calls_frac, total_time_frac, total_time, total_memory_in_frac, \
                total_memory_in, total_memory_out_frac, total_memory_out = \
                self.processor.frac_calculation(func, hits)

            total_memory_in = self.human_readable_size(total_memory_in)
            total_memory_out = self.human_readable_size(total_memory_out)

            col = self.node_color_func(calls_frac, total_time_frac)
            attribs = ['%s="%s"' % a for a in self.node_attributes.items()]
            print(attribs)
            node_str = '"%s" [%s];' % (func, ', '.join(attribs))
            if self.time_filter is None or self.time_filter.fraction <= total_time_frac:
                nodes.append(node_str % locals())

        # Define edges
        for fr_key, fr_val in self.processor.call_dict.items():
            if not fr_key: continue
            for to_key, to_val in fr_val.items():
                calls_frac, total_time_frac, total_time, total_memory_in_frac, total_memory_in, \
                   total_memory_out_frac, total_memory_out = self.processor.frac_calculation(to_key, to_val)
                col = self.edge_color_func(calls_frac, total_time_frac)
                edge = '[color = "%s", label="%s"]' % (col, to_val)
                if self.time_filter is None or self.time_filter.fraction < total_time_frac:
                    edges.append('"%s" -> "%s" %s;' % (fr_key, to_key, edge))

        defaults = '\n\t'.join(defaults)
        groups   = '\n\t'.join(groups)
        nodes    = '\n\t'.join(nodes)
        edges    = '\n\t'.join(edges)

        dot_fmt = (
            "digraph G {\n"
            "\t%(defaults)s\n\n"
            "\t%(groups)s\n\n"
            "\t%(nodes)s\n\n"
            "\t%(edges)s\n}\n"
        )
        return dot_fmt % locals()


class GraphvizImageOutput(GraphvizSourceOutput):

    def __init__(self):
        super(GraphvizImageOutput, self).__init__()
        self.output_file = 'pycallgraph.png'
        self.image_format = 'png'

    @classmethod
    def add_arguments(cls, subparsers):
        defaults = cls()

        subparser = subparsers.add_parser('graphviz-image',
            help='Graphviz image generation')

        subparser.add_argument('-o', '--output-file', type=str,
            default=defaults.output_file,
            help='The generated GraphViz image')

        subparser.add_argument('-t', '--output-type', type=str,
            default=defaults.image_format,
            help='Image format to product (png, ps, etc.)')

        cls.add_base_arguments(subparser)

    def done(self):
        source = super(GraphvizImageOutput, self).generate()
        print(source)

        # Create a temporary file to be used for the dot data
        fd, temp_name = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as f:
            f.write(source)

        cmd = '{} -T{} -o{} {}'.format(
            self.tool, self.image_format, self.output_file, temp_name
        )

        try:
            ret = os.system(cmd)
            if ret:
                raise PyCallGraphException( \
                    'The command "%(cmd)s" failed with error ' \
                    'code %(ret)i.' % locals())
        finally:
            os.unlink(temp_name)
