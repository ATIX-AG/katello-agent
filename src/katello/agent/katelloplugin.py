#
# Copyright (c) 2011 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#

"""
The katello agent plugin.
Configuration:
[reboot]
allow=1
delay=+1
"""

import sys
sys.path.append('/usr/share/rhsm')

import os
from logging import getLogger
from gofer.decorators import *
from gofer.agent.plugin import Plugin
from gofer.pmon import PathMonitor
from subscription_manager.certlib import ConsumerIdentity


log = getLogger(__name__)
plugin = Plugin.find(__name__)
cfg = plugin.cfg()

# plugin exports
package = Plugin.find('package')
Package = package.export('Package')
PackageGroup = package.export('PackageGroup')



def getbool(v):
    """
    Get string bool value.
    @param v: A string.
    @type v: str
    @return: True if v in (TRUE|YES|1)
    @rtype: bool
    """
    if v:
        return v.upper() in ('TRUE', 'YES', '1')
    else:
        return False


class RegistrationMonitor:
    
    pmon = PathMonitor()
    
    @classmethod
    @action(days=0x8E94)
    def init(cls):
        """
        Start path monitor to track changes in the
        rhsm identity certificate.
        """
        path = ConsumerIdentity.certpath()
        cls.pmon.add(path, cls.changed)
        cls.pmon.start()
        
    @classmethod
    def changed(cls, path):
        """
        A change in the rhsm certificate has been detected.
        When deleted: disconnect from qpid.
        When added/updated: reconnect to qpid.
        @param path: The changed file (ignored).
        @type path: str
        """
        log.info('changed: %s', path)
        if ConsumerIdentity.existsAndValid():
            cert = ConsumerIdentity.read()
            cls.bundle(cert)
            uuid = cert.getConsumerId()
            plugin.setuuid(uuid)
        else:
            plugin.setuuid(None)
    
    @classmethod
    def bundle(cls, cid):
        """
        Bundle the key and cert and write to a file.
        @param cid: A consumer id object.
        @type cid: L{ConsumerIdentity}
        @return: The path to written bundle.
        @rtype: str
        """
        path = os.path.join(cid.PATH, 'bundle.pem')
        f = open(path, 'w')
        try:
            f.write(cid.key)
            f.write(cid.cert)
            return path
        finally:
            f.close()

#
# API
#
  
class Packages:
    """
    Package management object.
    """
    
    def __init__(self, importkeys=False):
        """
        @param importkeys: Import GPG keys as needed.
        @type importkeys: bool
        """
        self.importkeys = importkeys

    @remote
    def install(self, names, reboot=False):
        """
        Install packages by name.
        @param names: A list of package names.
        @type names: [str,]
        @param reboot: Request reboot after packages are installed.
        @type reboot: bool
        @return: {installed=, reboot=}
          - installed : A list of installed packages
          - rebooted : A reboot was scheduled.
        @rtype: dict
        """
        p = Package(importkeys=self.importkeys)
        installed = p.install(names)
        log.info('Packages installed: %s', installed)
        if reboot and installed:
            scheduled = self.reboot()
        else:
            scheduled = False
        return dict(installed=installed, reboot_scheduled=scheduled)
    
    @remote
    def update(self, names, reboot=False):
        """
        Update packages by name.
        @param names: A list of package names.  Empty=ALL.
        @type names: [str,]
        @param reboot: Request reboot after packages are installed.
        @type reboot: bool
        @return: {updated=, reboot=}
          - updated : A list of (pkg, {updates=[],obsoletes=[]})
          - rebooted : A reboot was scheduled.
        @rtype: dict
        """
        p = Package(importkeys=self.importkeys)
        updated = p.update(names)
        log.info('Packages updated: %s', updated)
        if reboot and updated:
            scheduled = self.reboot()
        else:
            scheduled = False
        return dict(updated=updated, reboot_scheduled=scheduled)

    @remote
    def uninstall(self, names):
        """
        Uninstall packages by name.
        @param names: A list of package names.
        @type names: [str,]
        @return: A list of uninstalled packages
        @rtype: list
        """
        p = Package()
        uninstalled = p.uninstall(names)
        log.info('Packages uninstalled: %s', uninstalled)
        return uninstalled
    
    def reboot(self):
        """
        Schedule a sytem reboot.
        @return: True if scheduled.
        @rtype: bool
        """
        scheduled = False
        if getbool(cfg.reboot.allow):
            scheduled = True
            delay = cfg.reboot.delay
            os.system('shutdown -h %s &' % delay)
            log.info('rebooting in %s (min)', delay)
        return scheduled


class PackageGroups:
    """
    PackageGroup management object
    """
    
    def __init__(self, importkeys=False):
        """
        @param importkeys: Import GPG keys as needed.
        @type importkeys: bool
        """
        self.importkeys = importkeys

    @remote
    def install(self, names):
        """
        Install package groups by name.
        @param names: A list of package group names.
        @param names: str
        """
        g = PackageGroup(importkeys=self.importkeys)
        installed = g.install(names)
        log.info('Packages installed: %s', installed)
        return installed

    @remote
    def uninstall(self, names):
        """
        Uninstall package groups by name.
        @param names: A list of package group names.
        @type names: [str,]
        @return: A list of uninstalled packages
        @rtype: list
        """
        g = PackageGroup()
        uninstalled = g.uninstall(names)
        log.info('Packages uninstalled: %s', uninstalled)
        return uninstalled
