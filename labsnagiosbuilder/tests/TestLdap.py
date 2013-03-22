import unittest
from labsnagiosbuilder import build


class HostInfo(unittest.TestCase):
    def setUp(self):
        build.groups = {
            'ssh': {
                'description': 'SSH servers',
                'hosts': [],
                'puppet': ['base'],
            },
            'http': {
                'description': 'HTTP servers',
                'hosts': [],
                'puppet': ['webserver::apache2'],
            },
            'mysql': {
                'description': 'MySQL servers',
                'hosts': [],
                'puppet': ['role::labs-mysql-server'],
            },
            'lucene-frontend': {
                'description': 'Lucene frontend servers',
                'hosts': [],
                'puppet': ['role::lucene::front-end', 'role::lucene::front_end::poolbeta']
            },
        }

        self.instance1 = {
            'puppetVar': [
                'realm=labs',
                'instancecreator_email=damian@some-domain.invalid',
                'instancecreator_username=DamianZaremba',
                'instancecreator_lang=en',
                'instanceproject=bots',
                'instancename=bots-cb-dev'
            ],
            'associatedDomain': ['i-0000009e.pmtpa.wmflabs'],
            'aRecord': ['10.4.0.249'],
            'dc': ['i-000003d1'],
            'puppetClass': [
                'base',
                'ldap::client::wmf-test-cluster',
                'exim::simple-mail-sender',
                'sudo::labs_project'
            ]
        }

        self.instance2 = {
            'puppetVar': [
                'realm=labs',
                'instancecreator_email=damian@some-domain.invalid',
                'instancecreator_username=DamianZaremba',
                'instancecreator_lang=en',
                'instanceproject=bots',
                'instancename=bots-cb-dev-test'
            ],
            'associatedDomain': ['i-0000002d.pmtpa.wmflabs'],
            'aRecord': ['10.4.0.249'],
            'dc': ['i-000003d1'],
            'puppetClass': [
                'base',
                'ldap::client::wmf-test-cluster',
                'webserver::apache2',
                'exim::simple-mail-sender',
                'sudo::labs_project'
            ]
        }

    def test_groups1(self):
        expected_groups = ['ssh', 'bots']
        puppet_vars = build.get_puppet_vars(self.instance1)
        groups = build.get_host_groups(self.instance1, puppet_vars)
        self.assertEqual(sorted(groups), sorted(expected_groups))

    def test_groups2(self):
        expected_groups = ['ssh', 'bots', 'http']
        puppet_vars = build.get_puppet_vars(self.instance2)
        groups = build.get_host_groups(self.instance2, puppet_vars)
        self.assertEqual(sorted(groups), sorted(expected_groups))

    def test_get_puppet_vars1(self):
        expected_vars = {
            'realm': 'labs',
            'instancecreator_email': 'damian@some-domain.invalid',
            'instancecreator_username': 'DamianZaremba',
            'instancecreator_lang': 'en',
            'instanceproject': 'bots',
            'instancename': 'bots-cb-dev'
        }
        vars = build.get_puppet_vars(self.instance1)
        self.assertEqual(sorted(expected_vars), sorted(vars))

    def test_get_puppet_vars2(self):
        expected_vars = {
            'realm': 'labs',
            'instancecreator_email': 'damian@some-domain.invalid',
            'instancecreator_username': 'DamianZaremba',
            'instancecreator_lang': 'en',
            'instanceproject': 'bots',
            'instancename': 'bots-cb-dev-test'
        }
        vars = build.get_puppet_vars(self.instance2)
        self.assertEqual(sorted(expected_vars), sorted(vars))

    def test_host_info1(self):
        expected_host_info = {
            'puppet_classes': [
                'base',
                'ldap::client::wmf-test-cluster',
                'exim::simple-mail-sender',
                'sudo::labs_project'
            ],
            'fqdn': 'i-000003d1',
            'address': '10.4.0.249',
            'puppet_vars': {
                'realm': 'labs',
                'instancecreator_email': 'damian@some-domain.invalid',
                'instancecreator_username': 'DamianZaremba',
                'instancecreator_lang': 'en', 'instanceproject': 'bots',
                'instancename': 'bots-cb-dev'
            },
            'name': 'bots-cb-dev'
        }
        puppet_vars = build.get_puppet_vars(self.instance1)
        host_info = build.get_host_info(self.instance1, puppet_vars)
        self.assertEqual(sorted(expected_host_info), sorted(host_info))

    def test_host_info2(self):
        expected_host_info = {
            'puppet_classes': [
                'base',
                'ldap::client::wmf-test-cluster',
                'exim::simple-mail-sender',
                'sudo::labs_project',
                'webserver::apache2',
            ],
            'fqdn': 'i-000003d1',
            'address': '10.4.0.249',
            'puppet_vars': {
                'realm': 'labs',
                'instancecreator_email': 'damian@some-domain.invalid',
                'instancecreator_username': 'DamianZaremba',
                'instancecreator_lang': 'en', 'instanceproject': 'bots',
                'instancename': 'bots-cb-dev-test'
            },
            'name': 'bots-cb-dev-test'
        }
        puppet_vars = build.get_puppet_vars(self.instance2)
        host_info = build.get_host_info(self.instance2, puppet_vars)
        self.assertEqual(sorted(expected_host_info), sorted(host_info))
