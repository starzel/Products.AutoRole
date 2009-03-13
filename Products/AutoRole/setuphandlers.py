from StringIO import StringIO
from Products.PlonePAS.Extensions.Install import activatePluginInterfaces


def setup_auto_role_plugin(portal, out):
    uf = portal.acl_users
    ids = uf.objectIds()

    print >> out, "\nPlugin setup"

    AutoRole = uf.manage_addProduct['AutoRole']

    if 'auto_role' not in ids:
        AutoRole.addAutoRole('auto_role', 'Automatic Role Provider')
        print >> out, "Added AutoRole plugin."
        activatePluginInterfaces(portal, 'auto_role', out)


def importVarious(context):
    out = StringIO()

    portal = context.getSite()
    setup_auto_role_plugin(portal, out)
