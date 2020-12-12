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

### Release Testing

As others report testing with different OS/ZFS versions, I will add them
in for each tag. It's likely that this plugin works with relatively
new versions of Ubuntu, CentOS, and OmniOS versions, as the Python
and ZFS functions used rarely change.

#### Tested OS/ZFS versions (Release 1.5)

**NOTE: Dropping support for Python <3.5. Effectively, this means
Ubuntu <16.04.**

* Ubuntu 20.04, ZFS FS v5

#### Tested OS/ZFS versions (Release 1.4)

* Ubuntu 14.04 LTS, ZFS FS v5
* Ubuntu 16.04 LTS, ZFS FS v5
* Ubuntu 18.04 LTS, ZFS FS v5 
* Ubuntu 20.04 LTS, ZFS FS v5
* CentOS 7, ZFS FS v5
* OmniOS r151030

#### Other Releases

For testing on older releases, see the CHANGELOG associated with the tag.

### Example Nagios4 Configuration

This assumes you've set up a separate local configuration file include directory in your nagios.cfg
to store all of your local configs. One example would be:

```
cfg_dir=/usr/local/nagios/etc/objects/conf.d
```

This also assumes you've installed check_zfs.py to your nagios/libexec directory. One way would be to
softlink it to your directory where you've checked out the Git repository.

Below is an example set of command definitions which allow various levels of fidelity in zpool querying:

```
#Commands to check zpool status

define command {

    command_name    check_zpool_full
    command_line    $USER1$/check_zfs.py --capacity $ARG2$ $ARG3$ --fragmentation $ARG4$ $ARG5$ $ARG1$
}

define command {

    command_name    check_zpool_capacity
    command_line    $USER1$/check_zfs.py --capacity $ARG2$ $ARG3$ $ARG1$
}

define command {

    command_name    check_zpool
    command_line    $USER1$/check_zfs.py $ARG1$
}
```

Below is an example service definition using the above commands which will check the pool named "storage"
for both capacity (warn at 70%, critical at 85%) and fragmentation (warn at 30%, critical at 40%):

```
define service {
    use                     local-service
    host_name               localhost
    service_description     ZPOOL STORAGE
    check_command           check_zpool_full!storage!70!85!30!40
    notifications_enabled   1
}
```

Below is an example NRPE configuration which will accept the single argument "check_zpool" and run the
commands:

```
TODO
```
## Sudo Issues

The zfs command binaries that Check_ZFS_Linux uses to perform its checks are the following:

```
/sbin/zfs
/sbin/zpool
```

They need to be run as root in order to work properly. Since Nagios / NCPA / NRPE all typically
run as the user 'nagios', we need to give Nagios sudo access in order to run these binaries 
correctly. If Check_ZFS_Linux has problems sudo'ing to root, you'll see errors along these lines:

```
UNKNOWN : process must be run as root. Possible solution: add the following to your visudo: nagios ALL=NOPASSWD: Context: Zpool command - retval. Original command: "['/usr/bin/sudo', '-n', '/sbin/zpool', 'list', 'rpool']", then run check script with --nosudo option.
```

When debugging these issues, it may prove useful to run them from the host being monitored directly.
For example, here the check_zfs.py script succeeds when run as root:

```
root@hydrox:~/ncpa/plugins# whoami
root
root@hydrox:~/ncpa/plugins# ./check_zfs.py rpool
OK: POOL: rpool, STATUS: ONLINE, SIZE: 928G, ALLOC: 209G, FREE: 719G, DEDUP: 1.00x, COMPRESS: 1.11x, FRAG: 5%, CAP: 22% | frag=5%;;; cap=22%;;; dedup=1.00 compress_ratio=1.11 size=928.0GB;;; alloc=209.0GB;;; free=719.0GB;;; health=0;1;3; 
root@hydrox:~/ncpa/plugins# 
```

But when run as the 'nagios' user, it fails:

```
root@hydrox:~/ncpa/plugins# su nagios
$ whoami
nagios
$  ./check_zfs.py rpool
UNKNOWN : process must be run as root. Possible solution: add the following to your visudo: nagios ALL=NOPASSWD: Context: Zpool command - retval. Original command: "['/usr/bin/sudo', '-n', '/sbin/zpool', 'list', 'rpool']", then run check script with --nosudo option.
$
```

So, how do you fix this?

As the error suggests, try adding a line to the /etc/sudoers file for nagios. Best practice typically encourages you to use the visudo utility to do this editing. Here is what it might look like afterwards:

```
root@hydrox:/etc/sudoers.d# pwd
/etc/sudoers.d
root@hydrox:/etc/sudoers.d# ls -l
total 9
-r--r----- 1 root root 958 Feb  1 22:41 README
-r--r----- 1 root root 696 Jul 11 18:09 zfs
root@hydrox:/etc/sudoers.d# cat zfs
nagios ALL=NOPASSWD: /sbin/zfs
nagios ALL=NOPASSWD: /sbin/zpool
```

After you've given the nagios user access to run the zfs commands, try to run the check_zfs script again. Hopefully it now works, but if not, try using the '--nosudo' option.

```
root@hydrox:~/ncpa/plugins# su nagios
$ whoami
nagios
$ ./check_zfs.py rpool --nosudo
OK: POOL: rpool, STATUS: ONLINE, SIZE: 928G, ALLOC: 209G, FREE: 719G, DEDUP: 1.00x, COMPRESS: 1.11x, FRAG: 5%, CAP: 22% | frag=5%;;; cap=22%;;; dedup=1.00 compress_ratio=1.11 size=928.0GB;;; alloc=209.0GB;;; free=719.0GB;;; health=0;1;3; 
$
```

## Sample NCPA Configuration Example:

From commands.cfg on the Nagios host:
```
# 
# NCPA driven remote-ZFS check
# 
define command {
    #
    # Arg1 = token (community string)
    # Arg2 = ZFS pool name
    #
    command_name        check-zfs-on-remote-host
    command_line        $USER1$/check_ncpa.py -H $HOSTADDRESS$ -t $ARG1$ -M 'plugins/check_zfs.py' -a "$ARG2$ --nosudo"
}
```

From ncpa.cfg on the remote host being monitored:
```
#
# Extensions for plugins
# ----------------------
...

# Forcing move to python 3
.py = /usr/bin/python3 $plugin_name $plugin_args
```

Place check_zfs.py into the NCPA plugin's directory (/root/ncpa/plugins for example)



### SELinux ###

On systems with SELinux in enforcing mode nrpe is not granted the 
required permissions by SELinux, for that you can compile a policy
module, then a policy package that can then be installed.

A sample can be used as follows:
* Build a policy module: checkmodule -M -m -o check_zfs_py.mod contrib/SELinux/check_zfs_py.te
* Build a policy package: semodule_package -o check_zfs_py.pp -m check_zfs_py.mod
* Load the policy package: semodule -i check_zfs_py.pp

If you want to unload it: semodule -i check_zfs_py
