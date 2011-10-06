# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 Grid Dynamics
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import urlparse

from webob import exc

from nova import db
from nova import exception
from nova import flags
from nova import log as logging

from nova.api.openstack import extensions
from nova.api.openstack.contrib.admin_only import admin_only

FLAGS = flags.FLAGS

LOG = logging.getLogger('nova.api.contrib.networks')


def network_dict(network):
    if network:
        fields = (
        'bridge', 'vpn_public_port', 'dhcp_start', 'bridge_interface',
        'updated_at', 'id', 'cidr_v6', 'deleted_at',
        'gateway', 'label', 'project_id', 'vpn_private_address',
        'deleted',
        'vlan', 'broadcast', 'netmask', 'injected',
        'cidr', 'vpn_public_address', 'multi_host', 'dns1', 'host',
        'gateway_v6', 'netmask_v6', 'created_at')
        return dict((field, getattr(network, field)) for field in fields)
    else:
        return {}


def require_admin(f):
    def wraps(self, req, *args, **kwargs):
        if 'nova.context' in req.environ and\
           req.environ['nova.context'].is_admin:
            return f(self, req, *args, **kwargs)
        else:
            raise exception.AdminRequired()
    return wraps


class NetworkController(object):

    @require_admin
    def action(self, req, id, body):
        actions = {'disassociate': self._disassociate}
        for action, data in body.iteritems():
            try:
                return actions[action](req, id, body)
            except KeyError:
                msg = _("Network does not have %s action") % action
                raise exc.HTTPBadRequest(explanation=msg)
        msg = _("Invalid request body")
        raise exc.HTTPBadRequest(explanation=msg)

    def _disassociate(self, req, id, body):
        context = req.environ['nova.context']
        LOG.debug(_("Disassociating network with id %{query}s, "
                    "context %{context}s"),
                {"query": id, "context": context})
        try:
            net = db.network_get(context, int(id))
        except exception.NetworkNotFound:
            raise exc.HTTPNotFound()
        db.network_disassociate(context, net.id)
        return {'disassociated': int(id)}

    @require_admin
    def index(self, req):
        """Can filter projects """
        context = req.environ['nova.context']
        LOG.info(_("Getting networks with context %{ctxt}s"),
                 {"ctxt": context})
        networks = db.network_get_all(context)
        result = [network_dict(net_ref) for net_ref in networks]
        return  {'networks': result}

    @require_admin
    def show(self, req, id):
        context = req.environ['nova.context']
        LOG.info(_("Showing network with id %{query}s, context %{ctxt}s"),
                 {"query": id, "context": context})
        try:
            net = db.network_get(context, int(id))
        except exception.NetworkNotFound:
            raise exc.HTTPNotFound()
        return {'network': network_dict(net)}

    @require_admin
    def delete(self, req, id):
        context = req.environ['nova.context']
        LOG.audit(_("Deleting network with id %{query}s, context %{ctxt}s"),
                  {"query": context, "ctxt": context})
        try:
            net = db.network_get(context, int(id))
        except exception.NetworkNotFound:
            raise exc.HTTPNotFound()
        db.network_delete_safe(context, net.id)
        return exc.HTTPAccepted()

        # TODO(nsokolov): implement full CRUD, not done right in nova too


class Networks(extensions.ExtensionDescriptor):
    def __init__(self):
        pass

    def get_name(self):
        return "NetworkAdmin"

    def get_alias(self):
        return "NETWORK"

    def get_description(self):
        return "The Network API Extension"

    def get_namespace(self):
        return "http://docs.openstack.org/ext/os-networks/api/v1.1"

    def get_updated(self):
        return "2011-08-23 07:44:50.888131"

    @admin_only
    def get_resources(self):
        resources = []
        resources.append(extensions.ResourceExtension('os-networks',
                                                      NetworkController(),
                                                      member_actions={
                                                          'action': 'POST'}))
        return resources
