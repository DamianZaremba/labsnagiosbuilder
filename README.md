Labs Nagios Builder
===================
Simple python script to grab labs instances from ldap and build Nagios configs
for them.

Using a Puppet classes to determine hostgroups and services to monitor.

![http://travis-ci.org/#!/DamianZaremba/labsnagiosbuilder](https://secure.travis-ci.org/DamianZaremba/labsnagiosbuilder.png?branch=master)

How to add a check
==================
* Create or modify the relevant role file
* Provide any additional info in classes.ini

Puppet classes map 1-1 with / replacing :: ie
role::lucene::front_end::poolbeta -> templates/classes/role/lucene/front_end/poolbeta.cfg

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
