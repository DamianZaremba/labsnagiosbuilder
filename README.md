Labs Nagios Builder
===================
Simple python script to grab labs instances from ldap and build Nagios configs
for them.

Using a Puppet classes to determine hostgroups and services to monitor.

![http://travis-ci.org/#!/DamianZaremba/labsnagiosbuilder](https://secure.travis-ci.org/DamianZaremba/labsnagiosbuilder.png?branch=master)

How to set this up?
===================

* Clone the git repo (over http) out onto the server, we keep it in /root/
* Setup a crontab with the following (/etc/crontab)

	*/5 * * * * root cd /root/nagios-builder/labsnagiosbuilder/ && (git reset --hard; git pull origin master; ./build.py --ignored-hosts=/root/nagios-builder/wmflabs-ignored.host >> /var/log/nagios.log 2>&1)

* This will cause the repo to be reset, updated and then the build script run every 5min
* All reloading etc of icinga will happen based on changes


How to add a check
==================

* Create or modify the relevant role file
* Provide any additional info in classes.ini

Puppet classes map 1-1 with / replacing :: ie
role::lucene::front_end::poolbeta -> templates/classes/role/lucene/front_end/poolbeta.cfg

How to ignore an instance
=========================

* Create an entry in wmflabs-ignored.hosts with the hostname to ignore
* Use # or ; to add comments as to why

License
=======
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
