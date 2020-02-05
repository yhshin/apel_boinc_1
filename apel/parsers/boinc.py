'''
   Copyright 2014 The Science and Technology Facilities Council

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

   @author: Yun-Ha Shin
'''

import logging

from apel.db.records.event import EventRecord
from apel.parsers import Parser

# BlahdRecord
from apel.db.records.blahd import BlahdRecord
from apel.common import valid_from, valid_until, parse_timestamp

import platform               # hostname
from datetime import datetime

log = logging.getLogger(__name__)

thisnode = platform.node().split('.')[0]  # short hostname

#
def build_jobname(name):
    return thisnode + '.' + name  # NOTE: need to modify client.sql to increase JobName size

#
def get_boinc_conf_param(cp, name, default=None, type_=None):
    try:
        value = cp.get('boinc', name)
    except ConfigParser.NoOptionError as e:
        value = default
    if type_ == int and value is not None:
        value = int(value)
    log.info('[boinc/{0}] = {1}'.format(name, value))
    return value
    
#def get_int_boinc_conf_param(cp, name, default=None):
#    try:
#        value = cp.getint('boinc', name)
#    except ConfigParser.NoOptionError as e:
#        value = default
#    log.info('[boinc/{0}] = {1}'.format(name, value))
#    return value


class BoincParser(Parser):
    '''
    First implementation of the APEL parser for Boinc
    '''
    def __init__(self, site, machine_name, mpi):
        Parser.__init__(self, site, machine_name, mpi)
        log.info('Site: %s; batch system: %s' % (self.site_name, self.machine_name))

    #
    def set_boinc_params(self, cp):
        self._local_user_id = get_boinc_conf_param(cp, 'local_user_id', 'boinc')
        #self._local_user_group = get_boinc_conf_param(cp, 'local_user_group', None)
        self._infrastructure = get_boinc_conf_param(cp, 'infrastructure',
                                                    'APEL-BOINC-APEL-BOINC')
        #self._processors = get_int_boinc_conf_param(cp, 'processors', 1)
        self._processors = get_boinc_conf_param(cp, 'processors', 1, type_=int)
        #log.info('Boinc: localuserid={0}, infrastructure={1}, processors={2}'.format(
        #         self._local_userid, self._infrastructure, self._processors))

    #
    def parse(self, line):
        '''
        Parses single line from accounting log file.
        '''
        # endtime ue <ue> ct <cputime> fe <flops> nm <jobname> et <runtime> es <exit_status>
        
        values = line.strip().split()

        cputime = int(round(float(values[4])))

        mapping = {'Site'            : lambda x: self.site_name,
                   'MachineName'     : lambda x: self.machine_name,
                   'Infrastructure'  : lambda x: self._infrastructure,
                   'JobName'         : lambda x: build_jobname(x[8]),
                   'LocalUserID'     : lambda x: self._local_user_id,
                   'LocalUserGroup'  : lambda x: "",       # "atlas",
                   'WallDuration'    : lambda x: cputime,  # Di's suggestion
                   'CpuDuration'     : lambda x: cputime,
                   'StartTime'       : lambda x: int(x[0])-int(float(x[10])),
                   'StopTime'        : lambda x: int(x[0]),
                   #'MemoryReal'      : lambda x: 0,   # N/A in Boinc
                   #'MemoryVirtual'   : lambda x: 0,   # N/A in Boinc
                   'Processors'      : lambda x: self._processors,
                   'NodeCount'       : lambda x: 1
                  }

        rc = {}

        for key in mapping:
            rc[key] = mapping[key](values)

        record = EventRecord()
        record.set_all(rc)
        return record


class BoincBlahParser(Parser):
    '''
    First implementation of the APEL parser for Boinc to generate BlahdRecords
    '''
    def __init__(self, site, machine_name, mpi):
        Parser.__init__(self, site, machine_name, mpi)
        log.info('Site: %s; batch system: %s' % (self.site_name, self.machine_name))

    #
    def set_boinc_params(self, cp):   # set_vo(self, cp)
        self._vo = get_boinc_conf_param(cp, 'vo', 'atlas')
        #self._vo_role = self._get_boinc_conf_param(cp, 'vo_role', None)
        #self._vo_group = self._get_boinc_conf_param(cp, 'vo_group', None)
        #self._global_user_name = self._get_boinc_conf_param(cp, 'gloabl_user_name', None)
        #self._fqan = self._get_boinc_conf_param(cp, 'fqan', None)
        #log.info('BoincBlah: vo={0}'.format(self._vo))

    #
    def parse(self, line):
        '''
        Parses single line from accounting log file.
        '''
        # endtime ue <ue> ct <cputime> fe <flops> nm <jobname> et <runtime> es <exit_status>
        
        values = line.strip().split()

        timestamp = datetime.utcfromtimestamp(int(values[0])).strftime('%Y-%m-%d %H:%M:%S')
        utcdt = parse_timestamp(timestamp)

        # Simple mapping between keys in a log file and a table's columns
        mapping = {
            'TimeStamp'      : lambda x: 'T'.join(timestamp.split()) + 'Z',
            #'GlobalUserName': lambda x: '',
            #'FQAN'          : lambda x: '',
            'VO'             : lambda x: self._vo,
            #'VOGroup'       : lambda x: '',
            #'VORole'        : lambda x: '',
            'CE'             : lambda x: self.machine_name,
            #'GlobalJobId'   : lambda x: '',         # x[8]
            'LrmsId'         : lambda x: build_jobname(x[8]),
            'Site'           : lambda x: self.site_name,
            'ValidFrom'      : lambda x: valid_from(utcdt),
            'ValidUntil'     : lambda x: valid_until(utcdt),
            'Processed'      : lambda x: Parser.UNPROCESSED
        }

        rc = {}
        for key in mapping:
            rc[key] = mapping[key](values)

        record = BlahdRecord()
        record.set_all(rc)
        return record
