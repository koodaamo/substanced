import transaction
from pyramid_zodbconn import get_connection
from substanced.evolution import mark_unfinished_as_finished
from pyramid.httpexceptions import HTTPNotFound

from ..stats import statsd_incr
from ..interfaces import IReferenceRoot

def zodb_root_factory(request, t=transaction, g=get_connection,
                      mark_unfinished_as_finished=mark_unfinished_as_finished):
    # accepts "t", "g", and "mark_unfinished_as_finished" for unit testing
    # purposes only
    conn = g(request)
    zodb_root = conn.root()
    if not 'app_root' in zodb_root:
        registry = request.registry
        app_root = registry.content.create('Root')
        zodb_root['app_root'] = app_root
        t.savepoint() # give app_root a _p_jar
        mark_unfinished_as_finished(app_root, registry, t)
        t.commit()
    return zodb_root['app_root']

def root_factory(request, t=transaction, g=get_connection,
                 mark_unfinished_as_finished=mark_unfinished_as_finished):
    """ A function which can be used as a Pyramid ``root_factory``.  It accepts
    a request and returns an instance of the root content type for the rootname
    mentioned, or the default ZODB root if no rootname is mentioned."""
    statsd_incr('root_factory', rate=.1)
    matchdict = request.matchdict or {}
    name = matchdict.get('rootname', '')
    factory = request.registry.queryUtility(IReferenceRoot, name=name)
    if factory is None:
        raise HTTPNotFound(name)
    return factory(request)

def add_reference_root(config, factory, name):
    def register():
        config.registry.registerUtility(factory, IReferenceRoot, name=name)
        
    intr = config.introspectable(
        'substance d reference roots',
        name,
        config.object_description(factory),
        'substance d reference root'
        )
    
    intr['factory'] = factory
    intr['name'] = name
    
    config.action((IReferenceRoot, name), register, introspectables=(intr,))

def includeme(config): # pragma: no cover
    config.add_directive('add_reference_root', add_reference_root)
    config.add_reference_root(zodb_root_factory, '')
    config.add_reference_root(zodb_root_factory, 'zodb')