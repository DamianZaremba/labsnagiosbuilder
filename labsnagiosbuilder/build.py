#!/usr/bin/python
'''
Nagios config rebuild script for wmflabs.

Author: Damian Zaremba <damian@damianzaremba.co.uk>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
'''
# Import modules we need
import sys
import os
import ldap
import logging
import subprocess
from optparse import OptionParser
from jinja2 import Environment, PackageLoader
import ConfigParser

# Are we in debug mode?
debug_mode = False

# Where we dump the generated configs
nagios_config_dir = "/etc/icinga/objects"

# Instances to ignore
ignored_fqdns = []

# Configs to ignore on cleanup
ok_files = ['localhost_icinga',
            'services_icinga',
            'ido2db_check_proc',
            'hostgroups_icinga',
            'extinfo_icinga',
            'contacts_icinga',
            'timeperiods_icinga']

# How much to spam
logging_level = logging.INFO

# Path to classes mapping file
classes_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'classes.ini')

# Path to ignored hosts file
ignored_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'ignored.host')

# LDAP details
ldap_config_file = "/etc/ldap.conf"
ldap_base_dn = "dc=wikimedia,dc=org"
ldap_filter = '(objectClass=dcobject)'
ldap_attrs = ['puppetVar', 'puppetClass', 'dc', 'aRecord', 'associatedDomain']

# Hostgroups we know of - projects get auto added here
groups = {}

# Setup logging, everyone likes logging
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.setLevel(logging_level)
logger.addHandler(stdout_handler)


def get_ldap_config():
    '''
    Simple function to load the ldap config into a dict
    '''
    ldap_config = {}
    with open(ldap_config_file, 'r') as fh:
        for line in fh.readlines():
            line_parts = line.split(' ', 1)

            if len(line_parts) == 2:
                ldap_config[line_parts[0].strip()] = line_parts[1].strip()

    return ldap_config


def ldap_connect():
    '''
    Simple function to connect to ldap
    '''
    ldap_config = get_ldap_config()
    if 'uri' not in ldap_config:
        logger.error('Could get URI from ldap config')
        return False

    if 'binddn' not in ldap_config or 'bindpw' not in ldap_config:
        logger.error('Could get bind details from ldap config')
        return False

    ldap_connection = ldap.initialize(ldap_config['uri'])
    ldap_connection.start_tls_s()

    try:
        ldap_connection.simple_bind_s(ldap_config['binddn'],
                                      ldap_config['bindpw'])
    except ldap.LDAPError:
        logger.error('Could not bind to LDAP')
    else:
        logger.debug('Connected to ldap')
        return ldap_connection


def ldap_disconnect(ldap_connection):
    '''
    Simple function to disconnect from ldap
    '''
    try:
        ldap_connection.unbind_s()
    except ldap.LDAPError:
        logger.error('Could not cleanly disconnect from LDAP')
    else:
        logger.debug('Disconnected from ldap')


def get_host_groups(instance, puppet_vars):
    '''
    Function to determine what groups an instance should belong to
    '''
    logger.debug('Processing host groups for %s' % instance['dc'][0])
    host_groups = []

    # Add it to the project group
    if 'instanceproject' in puppet_vars:
        project = puppet_vars['instanceproject']
        logger.debug('Added group %s for %s' % (project, instance['dc'][0]))

        # Create the project group if it doesn't exist
        if project not in groups.keys():
            groups[project] = {
                'description': '%s project' % project,
                'hosts': [],
            }
        host_groups.append(project)

    # Figure out stuff from puppet classes :)
    if 'puppetClass' in instance.keys():
        for group in groups.keys():
            for puppet_class in instance['puppetClass']:
                if ('puppet' in groups[group] and puppet_class in
                        groups[group]['puppet']):

                    logger.debug('Added group %s for %s' % (
                                 puppet_class, instance['dc'][0]))
                    host_groups.append(group)

    return host_groups


def get_puppet_vars(instance):
    '''
    Function to determine what puppet vars an instance has
    '''
    logger.debug('Processing puppet vars for %s' % instance['dc'][0])
    vars = {}
    if 'puppetVar' in instance.keys():
        for var in instance['puppetVar']:
            (k, v) = var.split('=', 1)
            logger.debug('Found puppet var %s for %s' %
                         (k, instance['dc'][0]))
            vars[k] = v

    return vars


def get_host_info(instance, puppet_vars):
    '''
    Function to grab host info we need to build the definition
    '''
    logger.debug('Processing instance info for %s' % instance['dc'][0])
    info = {}

    info['fqdn'] = instance['dc'][0]
    for domain in instance['associatedDomain']:
        if domain.startswith(puppet_vars['instancename']):
            info['fqdn'] = domain

    info['name'] = puppet_vars['instancename']
    info['address'] = instance['aRecord'][0]
    info['puppet_vars'] = puppet_vars
    info['puppet_classes'] = instance['puppetClass']

    return info


def get_monitoring_info(ldap_connection):
    '''
    Function to do a ldap search and return hosts and groups
    '''
    hosts = {}

    logger.debug('Searching ldap for hosts')
    results = ldap_connection.search_s(ldap_base_dn, ldap.SCOPE_SUBTREE,
                                       ldap_filter, ldap_attrs)
    if not results:
        logger.error('Could not get the list of hosts from ldap')

    for (dn, instance) in results:
        logger.debug('Processing info for %s' % dn)

        # Get puppet vars
        puppet_vars = get_puppet_vars(instance)

        # Get the dc - don't rely on this for anything other than
        # being unique (used for file names etc)
        dc = instance['dc'][0]

        # We only care about instances
        if 'instancename' not in puppet_vars:
            logger.debug('Skipping %s, not an instance' % dn)
            continue

        # If an instance doesn't have an ip it's probably building
        ips = []
        for ip in instance['aRecord']:
            if len(ip.strip()) > 0:
                ips.append(ip)

        if len(ips) == 0:
            logger.debug('Skipping %s, no ips' % dn)
            continue

        # Sort out the host it's self
        hosts[dc] = get_host_info(instance, puppet_vars)

        # Check if we're ignoring this instance
        if hosts[dc]['fqdn'] in ignored_fqdns:
            del(hosts[dc])
            logger.info('Skipping %s due to ignore' % dn)
            continue

        # Sort out our groups
        host_groups = get_host_groups(instance, puppet_vars)
        for group in host_groups:
            logger.debug('Adding group %s for %s' % (group, dn))
            groups[group]['hosts'].append(hosts[dc]['fqdn'])
        hosts[dc]['groups'] = host_groups

        # Sort our monitoring classes out
        hosts[dc]['monitoring_class_files'] = []
        base_path = os.path.dirname(os.path.abspath(__file__))
        for pclass in hosts[dc]['puppet_classes']:
            pclass = '/'.join(pclass.split('::'))
            mclass_file = "%s.cfg" % os.path.join('classes', pclass)
            fmclass_file = os.path.abspath(os.path.join(
                base_path, 'templates', mclass_file))

            if not fmclass_file.startswith(base_path):
                logging.debug('Skipping %s as it looks dodgy' % mclass_file)
                continue

            if os.path.isfile(fmclass_file):
                hosts[dc]['monitoring_class_files'].append(mclass_file)

    return hosts


def write_nagios_configs(hosts):
    jinja2_env = Environment(loader=PackageLoader('labsnagiosbuilder',
                                                  'templates'))

    template = jinja2_env.get_template('group.cfg')
    for group in groups.keys():
        if len(groups[group]['hosts']) == 0:
            logger.info('Skipping group %s (0 hosts)', group)
            continue
        file_path = os.path.join(nagios_config_dir, 'group-%s.cfg' % group)
        with open(file_path, 'w') as fh:
            logger.debug('Writing out group %s to %s' % (group, file_path))
            fh.write(template.render(group_name=group, group=groups[group]))
            fh.close()

    template = jinja2_env.get_template('host.cfg')
    for host in hosts.keys():
        file_path = os.path.join(nagios_config_dir, 'instance-%s.cfg' %
                                 hosts[host]['fqdn'])
        with open(file_path, 'w') as fh:
            logger.debug('Writing out host %s to %s' % (host, file_path))
            fh.write(template.render(host=hosts[host]))
            fh.close()

    logger.info('Dumped nagios configs')
    return True


def clean_nagios(hosts):
    '''
    Simple function to remove old instances
    '''
    remove_files = []

    for file_path in os.listdir(nagios_config_dir):
        cfg = file_path[:-4]

        # Old instances
        if not cfg.startswith('instance-') and not cfg.startswith('generic') \
                and cfg not in ok_files:
            remove_files.append(file_path)

        # Old groups
        if cfg.startswith('group-') and cfg[6:] not in groups.keys():
            remove_files.append(file_path)

    for cfg in remove_files:
        file_path = os.path.join(nagios_config_dir, cfg)
        logger.info('Removing %s' % file_path)
        os.unlink(file_path)


def reload_nagios():
    '''
    Simple function to reload nagios
    '''
    if subprocess.call("icinga -v /etc/icinga/icinga.cfg", shell=True) != 0:
        logger.error('Nagios config validation failed')
        return

    logger.info('Reloading nagios')
    os.system('service icinga reload')
    return True


def load_ignored(classes_path):
    '''
    Loads the ignored hosts list from a file if it exists
    '''
    if os.path.isfile(ignored_path):
        with open(ignored_path, 'r') as fh:
            for line in fh.readlines():
                line = line.strip()

                # Ignore blank lines
                if len(line) == 0:
                    continue

                # Ignore comments
                if line.startswith('#') or line.startswith(';'):
                    continue

                ignored_fqdns.append(line)


def load_groups(classes_path):
    '''
    Loads the classes mapping from a file if it exists
    '''
    if not os.path.isfile(classes_path):
        return

    config = ConfigParser.RawConfigParser()
    config.read(classes_path)
    for section in config.sections():
        short = config.get(section, 'short')
        if not short:
            logger.debug('Skipping %s as no desc' % section)

        if short not in groups.keys():
            desc = config.get(section, 'desc')
            if not desc:
                logger.debug('Skipping %s as no desc' % section)

            groups[short] = {'description': desc, 'hosts': [], 'puppet': []}
        groups[short]['puppet'].append(section)


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option('-d', '--debug', action='store_true', dest='debug')
    parser.add_option('--config-dir', dest='config_dir')
    parser.add_option('--ignored-hosts', dest='ignored_path')
    parser.add_option('--class-mappings', dest='classes_path')

    (options, args) = parser.parse_args()
    if options.debug:
        logger.setLevel(logging.DEBUG)
        debug_mode = True

    if options.config_dir:
        nagios_config_dir = options.config_dir

    if (not os.path.isdir(nagios_config_dir)
            and not os.makedirs(nagios_config_dir)):
        logger.error('Could not create config dir')
        sys.exit(2)

    # Fix the path to include our directory in the path
    # Needed for jinja2 to work
    sys.path.insert(0, os.path.dirname(
                    os.path.dirname(
                        os.path.abspath(__file__))))

    # Load the group info
    load_groups(classes_path)

    # Load the ignored info
    load_ignored(ignored_path)

    # Connect
    ldap_connection = ldap_connect()
    if ldap_connection:
        # Grab the hosts
        hosts = get_monitoring_info(ldap_connection)
        ldap_disconnect(ldap_connection)

        # Write and exit
        if write_nagios_configs(hosts):
            clean_nagios(hosts)
            if not debug_mode:
                if reload_nagios():
                    sys.exit(0)
            else:
                logger.debug('Skipping reload due to debug mode')

        sys.exit(1)
