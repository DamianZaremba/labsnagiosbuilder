import unittest
from labsnagiosbuilder import build


class HostInfo(unittest.TestCase):
    def setUp(self):
        self.instance1 = {
            'puppetVar': [
                'realm=labs',
                'instancecreator_email=damian@some-domain.invalid',
                'instancecreator_username=DamianZaremba',
                'instancecreator_lang=en',
                'instanceproject=bots',
                'instancename=bots-cb'
            ],
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
        groups = build.get_host_groups(self.instance1)
        self.assertEqual(set(groups)-set(expected_groups), set([]))

    def test_groups2(self):
        expected_groups = ['ssh', 'bots', 'http']
        groups = build.get_host_groups(self.instance2)
        self.assertEqual(set(groups)-set(expected_groups), set([]))

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
        self.assertEqual(set(vars)-set(expected_vars), set([]))

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
        self.assertEqual(set(vars)-set(expected_vars), set([]))

    def test_host_info1(self):
        expected_host_info = {
            'puppet_classes': [
                'base',
                'ldap::client::wmf-test-cluster',
                'exim::simple-mail-sender',
                'sudo::labs_project'
            ],
            'fqdn': 'i-000003d1',
            'groups': ['bots', 'ssh'],
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
        host_info = build.get_host_info(self.instance1)
        self.assertEqual(set(host_info)-set(expected_host_info), set([]))

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
            'groups': ['bots', 'ssh'],
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
        host_info = build.get_host_info(self.instance2)
        self.assertEqual(set(host_info)-set(expected_host_info), set([]))
