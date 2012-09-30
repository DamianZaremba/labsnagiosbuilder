#!/usr/bin/python
'''
Nagios config rebuild script for wmflabs.

Author: Damian Zaremba <damian@damianzaremba.co.uk>

This program is free software. It comes without any warranty, to
the extent permitted by applicable law. You can redistribute it
and/or modify it under the terms of the Do What The Fuck You Want
To Public License, Version 2, as published by Sam Hocevar. See
http://sam.zoy.org/wtfpl/COPYING for more details.
'''
# Import modules we need
import sys
import os
import re
import ldap
import logging
import subprocess
from optparse import OptionParser
from jinja2 import Environment, PackageLoader

# Are we in debug mode?
debug_mode = False

# Where we dump the generated configs
nagios_config_dir = "/etc/nagios3/conf.d"

# How much to spam
logging_level = logging.INFO

# LDAP details
ldap_config_file = "/etc/ldap.conf"
ldap_base_dn = "dc=wikimedia,dc=org"
ldap_filter = '(objectClass=dcobject)'
ldap_attrs = ['puppetVar', 'puppetClass', 'dc', 'aRecord', 'associatedDomain']

# Hostgroups we know of - projects get auto added here
groups = {
    # Group name
    'ssh': {
        # Group Description
        'description': 'SSH servers',
        # Hosts in group - we fill this in
        'hosts': [],
        # Puppet classes that cause hosts to be added to this group ;)
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
}

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
                if 'puppet' in groups[group] and \
                puppet_class in groups[group]['puppet']:
                    logger.debug('Added group %s for %s' %
                                    (puppet_class, instance['dc'][0]))
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
        if domain.startswith(instance['dc'][0]):
            info['fqdn'] = domain

    info['uname'] = puppet_vars['instancename']
    matches = re.match('dc=.+,dc=(.+),.+', instance['dc'][0])
    if matches and matches.group(1):
        info['uname'] = "%s-%s" % (matches.group(1),
                                    puppet_vars['instancename'])

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

        # Sort out our groups
        host_groups = get_host_groups(instance, puppet_vars)
        for group in host_groups:
            logger.debug('Adding group %s for %s' % (group, dn))
            groups[group]['hosts'].append(hosts[dc]['fqdn'])
        hosts[dc]['groups'] = host_groups

    return hosts


def write_nagios_configs(hosts):
    jinja2_env = Environment(loader=PackageLoader('labsnagiosbuilder',
                                                    'templates'))

    template = jinja2_env.get_template('group.cfg')
    for group in groups.keys():
        file_path = os.path.join(nagios_config_dir, 'group-%s.cfg' % group)
        with open(file_path, 'w') as fh:
            logger.debug('Writing out group %s to %s' % (group, file_path))
            fh.write(template.render(group_name=group, group=groups[group]))
            fh.close()

    template = jinja2_env.get_template('host.cfg')
    for host in hosts.keys():
        file_path = os.path.join(nagios_config_dir, '%s.cfg' % host)
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
        if cfg.startswith('i-') and cfg not in hosts.keys():
            remove_files.append(file_path)

        # Old groups
        if cfg.startswith('group-') and \
        cfg[6:] not in groups.keys():
            remove_files.append(file_path)

    for cfg in remove_files:
        file_path = os.path.join(nagios_config_dir, cfg)
        logger.info('Removing %s' % file_path)
        os.unlink(file_path)


def reload_nagios():
    '''
    Simple function to reload nagios
    '''
    if subprocess.call("nagios3 -v /etc/nagios3/nagios.cfg", shell=True) != 0:
        logger.error('Nagios config validation failed')
        return

    logger.info('Reloading nagios')
    os.system('service nagios3 reload')
    return True

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option('-d', '--debug', action='store_true', dest='debug')
    parser.add_option('--config-dir', dest='config_dir')

    (options, args) = parser.parse_args()
    if options.debug:
        logger.setLevel(logging.DEBUG)
        debug_mode = True

    if options.config_dir:
        nagios_config_dir = options.config_dir

    if not os.path.isdir(nagios_config_dir) and \
    not os.makedirs(nagios_config_dir):
        logger.error('Could not create config dir')
        sys.exit(2)

    # Fix the path to include our directory in the path
    # Needed for jinja2 to work
    sys.path.insert(0, os.path.dirname(
                    os.path.dirname(
                        os.path.abspath(__file__))))

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
