Check_ZFS_Linux
===============

A plugin to check ZFS pools in Linux
------------------------------------

Author: Zachary LaCelle

License: GPLv3

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

### Description

This is a python script which will check the health, capacity,
fragmentation, and other things for use with Nagios monitoring.

It provides perfdata feedback as well.

### Currently tested OS/ZFS versions
* Ubuntu 14.04 LTS, ZFS v5
* Ubuntu 16.04 LTS, ZFS v5
* CentOS 7, ZFS v5

### SELinux ###

On systems with SELinux in enforcing mode nrpe is not granted the 
required permissions by SELinux, for that you can compile a policy
module, then a policy package that can then be installed.

A sample can be used as follows:
* Build a policy module: checkmodule -M -m -o check_zfs_py.mod contrib/SELinux/check_zfs_py.te
* Build a policy package: semodule_package -o check_zfs_py.pp -m check_zfs_py.mod
* Load the policy package: semodule -i check_zfs_py.pp

If you want to unload it: semodule -i check_zfs_py
