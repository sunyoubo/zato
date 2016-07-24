# -*- coding: utf-8 -*-

"""
Copyright (C) 2016, Zato Source s.r.o. https://zato.io

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

# stdlib
from contextlib import closing
from traceback import format_exc
from uuid import uuid4

from cryptography.fernet import Fernet

# Zato
from zato.common import SEC_DEF_TYPE
from zato.common.broker_message import SECURITY
from zato.common.odb.model import Cluster, JWT
from zato.common.odb.query import jwt_list
from zato.server.service.internal import AdminService, AdminSIO, ChangePasswordBase, GetListAdminSIO


class GetList(AdminService):
    """ Returns the list of JWT definitions available.
    """
    _filter_by = JWT.name,

    class SimpleIO(GetListAdminSIO):
        request_elem = 'zato_security_jwt_get_list_request'
        response_elem = 'zato_security_jwt_get_list_response'
        input_required = ('cluster_id',)
        output_required = ('id', 'name', 'is_active', 'username')

    def get_data(self, session):
        return self._search(jwt_list, session, self.request.input.cluster_id, None, False)

    def handle(self):
        with closing(self.odb.session()) as session:
            self.response.payload[:] = self.get_data(session)


class Create(AdminService):
    """ Creates a new JWT definition.
    """
    class SimpleIO(AdminSIO):
        request_elem = 'zato_security_jwt_create_request'
        response_elem = 'zato_security_jwt_create_response'
        input_required = ('cluster_id', 'name', 'is_active', 'username')
        output_required = ('id', 'name')

    def handle(self):
        input = self.request.input
        input.password = uuid4().hex
        input.secret = Fernet.generate_key()

        with closing(self.odb.session()) as session:
            try:
                cluster = session.query(Cluster).filter_by(id=input.cluster_id).first()

                # Let's see if we already have a definition of that name before committing
                # any stuff into the database.
                existing_one = session.query(JWT).\
                    filter(Cluster.id==input.cluster_id).\
                    filter(JWT.name==input.name).first()

                if existing_one:
                    raise Exception('JWT definition [{0}] already exists on this cluster'.format(input.name))

                auth = JWT(None, input.name, input.is_active, input.username, input.password, input.secret, cluster)

                session.add(auth)
                session.commit()

            except Exception, e:
                msg = 'Could not create a JWT definition, e:[{e}]'.format(e=format_exc(e))
                self.logger.error(msg)
                session.rollback()

                raise
            else:
                input.action = SECURITY.JWT_CREATE.value
                input.sec_type = SEC_DEF_TYPE.JWT
                input.id = auth.id
                self.broker_client.publish(input)

            self.response.payload.id = auth.id
            self.response.payload.name = auth.name


class Edit(AdminService):
    """ Updates a JWT definition.
    """
    class SimpleIO(AdminSIO):
        request_elem = 'zato_security_jwt_edit_request'
        response_elem = 'zato_security_jwt_edit_response'
        input_required = ('id', 'cluster_id', 'name', 'is_active', 'username')
        output_required = ('id', 'name')

    def handle(self):
        input = self.request.input
        with closing(self.odb.session()) as session:
            try:
                existing_one = session.query(JWT).\
                    filter(Cluster.id==input.cluster_id).\
                    filter(JWT.name==input.name).\
                    filter(JWT.id!=input.id).\
                    first()

                if existing_one:
                    raise Exception('JWT definition [{0}] already exists on this cluster'.format(input.name))

                definition = session.query(JWT).filter_by(id=input.id).one()
                old_name = definition.name

                definition.name = input.name
                definition.is_active = input.is_active
                definition.username = input.username

                session.add(definition)
                session.commit()

            except Exception, e:
                msg = 'Could not update the JWT definition, e:[{e}]'.format(e=format_exc(e))
                self.logger.error(msg)
                session.rollback()

                raise
            else:
                input.action = SECURITY.JWT_EDIT.value
                input.old_name = old_name
                input.sec_type = SEC_DEF_TYPE.JWT
                self.broker_client.publish(input)

                self.response.payload.id = definition.id
                self.response.payload.name = definition.name


class ChangePassword(ChangePasswordBase):
    """ Changes the password of a JWT definition.
    """
    password_required = False

    class SimpleIO(ChangePasswordBase.SimpleIO):
        request_elem = 'zato_security_jwt_change_password_request'
        response_elem = 'zato_security_jwt_change_password_response'

    def handle(self):
        def _auth(instance, password):
            instance.password = password

        return self._handle(JWT, _auth, SECURITY.JWT_CHANGE_PASSWORD.value)


class Delete(AdminService):
    """ Deletes a JWT definition.
    """
    class SimpleIO(AdminSIO):
        request_elem = 'zato_security_jwt_delete_request'
        response_elem = 'zato_security_jwt_delete_response'
        input_required = ('id',)

    def handle(self):
        with closing(self.odb.session()) as session:
            try:
                auth = session.query(JWT).\
                    filter(JWT.id==self.request.input.id).\
                    one()

                session.delete(auth)
                session.commit()
            except Exception, e:
                msg = 'Could not delete the JWT definition, e:[{e}]'.format(e=format_exc(e))
                self.logger.error(msg)
                session.rollback()

                raise
            else:
                self.request.input.action = SECURITY.JWT_DELETE.value
                self.request.input.name = auth.name
                self.broker_client.publish(self.request.input)