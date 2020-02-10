# An adaptation of APEL parser to handle BOINC job logs

## An example BOINC job log line

`1581252044 ue 5362.095746 ct 19643.120000 fe 43200000000000 nm VKdLDmsflKwnsSi4apGgGQJmABFKDmABFKDm1VzYDmABFKDm0ySwQm_0 et 5922.558134 es 0`

The following boinc code explains the fields in the line 
```
    fprintf(f, "%.0f ue %f ct %f fe %.0f nm %s et %f es %d\n",
        gstate.now, estimated_runtime_uncorrected(), final_cpu_time,
        wup->rsc_fpops_est, name, final_elapsed_time,
        exit_status
    );
```
We can use the fields 0, 4, 8,and 10 for boinc job accounting as `endTime`, `cpuTime`, `jobName`
and `elapsedTime`, respectively.


## Records to be filled by the parser

APEL parsers parse job logs to fill two types of records, EventRecord and BlahdRecord, which in
turn be used to populate two corresponding tables, EventRecords and BlahdRecords.

EventRecord        | BlahdRecord
-------------------|---------------
***Site***         | Site
MachineName        | CE
Infrastructure     | GlobalUserName
***JobName***      | LrmsId
LocalUserID        | GlobalJobId
LocalUserGroup     | VO
***CpuDuration***  | VOGroup
***WallDuration*** | VORole
***StartTime***    | FQAN
***StopTime***     | TimeStamp
MemoryReal         | ValidFrom
MemoryVirtual      | ValidUntil
Processors         | Processed
NodeCount          |


The fields in ***bold italic*** fonts are mandatory according to
[APEL/MessageFormat](https://wiki.egi.eu/wiki/APEL/MessageFormat).

Since BOINC job log contains very limited information, many fields must be filled with some kinds
of conventions.


### A note about parsing BOINC job logs

There is no blah logs for BOINC jobs so there needs a second parser to generate BlahdRecords for
BOINC jobs.  A way to do it parsing the same job log file twice; one for EventRecord and the other
for BlahdRecord.

Technically, parsing the same file twice requires to set a configuration parameter,
`reparse = true`, which will replace existing records.  This raises a scalability issue as the
job logs is growing and the number of worker nodes is increasing.  There may be many ways to
avoid replacing existing records by skipping parsing old logs.  This adaption uses DB to get
latest EndTime of the jobs ran on the node where the parser is running, and skips parsing logs
older than that.


### Mandatory fields for site accounting

The following mandatory fields essential to site accounting can be filled with values from
BOINC job logs.

Field        | Value
-------------|------------------------
Site         | site name
StartTime    | `endTime - elapsedTime`
StopTime     | `endTime`
CpuDuration  | `cpuTime`
WallDuration | (see note below)

Some fields also can be set easily with information from job logs, and other fields can be filled
with arbitrary values as described in following sections.


### A note about `WallDuration`, `Processors` and `NodeCount`

Usually BOINC jobs run with low CPU priority so total walltime obtained by simply multiplying
elapsed time by number of cores would be an overestimation, for non-boinc jobs with higher
priorites could have been running while boinc jobs were running.

An idea suggested by a local expert (Di) is to use cputime as walltime, which seems be a reasonable
estimation.  To use this estimation, Processors has to be set to 1.  The job runs on a single
node, NodeCount can be set to 1 too.

Field        | Value
-------------|------------------------
WallDuration | `cpuTime`
Processrs    | 1
NodeCount    | 1



### Other non-mandatory fields that can be filled with data from job logs 

The following fields can be filled with the values on the right column.

Field       | Value
------------|-----------------------------------
LocalUserId | local user name for boinc jobs (eg, boinc)
TimeStamp   | `endTime`
ValidFrom   | `valid_from(endTime)`
ValidUntil  | `valid_until(endTime)`
Processed   | `Parser.UNPROCESSED`


### A set of conventions for the other fields

The remaining feilds except for `JobName` can't be determined by boic job logs itself.  Thus they
must be set with arbitrary values.  Here is a set of conventions used in this adaptation.


#### 1. JobName, LrmsId and GlobalJobId

A boinc job name (`jobName`) is already a global id so it can be used as `GlobalJobId` as it is.
It can also be used as `LocalJobId` (which is `JobName`) but it would be useful to add woker node
information to `LocalJobId`.  But `JobName` is `VARCHAR(60)` while `jobName` is 56 chars so it
needs to reduce it to combine worker node with it to build `LocalJobId`.

A simple method is to concatenate worker node name and truncated `jobName`.  For example,
```
  LocalJobId = JobName = shortHostName + '.' + jobName[:N]
```
If necessary, `endTime` can be added too to ensure uniqueness of LocalJobId.


**Note** that the same naming convention must be applied to `LrmsId`.


#### 2. MachineName and CE

`EventRecord.MachineName` and `BlahdRecord.CE` become `MachineName` and `SubmitHost` in JobRecord,
respectively.  `MachineName` seems not being used anywhere so it can be named arbitrarily.

`SumitHost` is used in grouping jobs to normalize their cpu and wall times with given spec values.
Even though it's possible to use one of existing submit host names for `CE`, it would be better to
define a new submit host name for BOINC jobs.  Its spec type and spec value can be configured in
`client.cfg` file.  

A simple solution is to use name of the APEL clinet node publishing BOINC accounting messages to
APEL server.  For example,
```
  boinc.lcg.trumf.ca
```


#### 3. Infrastructure

According to [APEL/MessageFormat](https://wiki.egi.eu/wiki/APEL/MessageFormat) wiki, it is
`<accounting client>-<CE type>-<batch system type>`.  CE and batch system types for BOINC jobs
are not well-defined so we may assign arbitrary type names, for example,
```
  APEL-BOINC-BOINC
```


### Configuration of the above fields

Values of the above fields can be configured in config files; `parser.cfg` and `client.cfg`.

* parser.cfg
```
  [site_info]
  site_name = <site>
  lrms_server = <er_machine_name>

  [boinc]
  # event records
  local_user_id = boinc
  infrastructure = APEL-BOINC-BOINC
  processors = 1
  # blahd records
  vo = atlas
```

* client.cfg
```
  [spec_updater]
  site_name = <site>
  manual_spec1 = <sr_ce_name>,<spec_type>,<spec_level>
```

To make it simple, `site_info/lrms_server` is used for both `EventRecord.MachineName` and
`BlahdRecord.CE`.  Note that `BlahdRecord.CE` and `<sr_ce_name>` must be the same to set proper
`spec_type` and `spec_value` for BOINC jobs.

If wanted to distinguish `MachineName` and `SubmiHost` name, another option can be added in
`[boinc]` section to set `<br_ce_name>`.
For example,
```
  [boinc]
  ce_name = <br_ce_name>
```

`conf/parser-boinc.cfg` and `conf/client-boinf.cfg` are example config files for boinc jobs.


### Feilds left undefined

The following non-mandatory fields are left undefined in this adaptation

* EventRecord
  - LocalUserGroup
  - MamoryReal
  - MemoryVirtual

* BlahdRecord
  - GlobalUserName
  - FQAN
  - VOGroup
  - VORole


## Example messages generated by `apelclient` from the above information

Then APEL client uses the records in the above tables to creates job records to be published as
either individual jobs or summaries.

**NOTE** that it is _recommended_ to send **summary messages** instead of sending individual job
messages.  


### An individual job message

```
  APEL-individual-job-message: v0.3
  Site: TRIUMF-LCG2
  SubmitHost: boinc.lcg.triumf.ca
  MachineName: boinc.lcg.triumf.ca
  Queue: None
  LocalJobId: wns0010.077NDmViIGwnsSi4apGg
  LocalUserId: boinc
  GlobalUserName: None
  FQAN: None
  VO: atlas
  VOGroup: None
  VORole: None
  WallDuration: 23341
  CpuDuration: 23341
  Processors: 1
  NodeCount: 1
  StartTime: 1580216440
  EndTime: 1580224397
  InfrastructureDescription: APEL-BOINC-BOINC
  InfrastructureType: grid
  MemoryReal: None
  MemoryVirtual: None
  ServiceLevelType: HEPSPEC
  ServiceLevel: 21.69
  %%
```

### A summary message

```
  APEL-summary-job-message: v0.2
  Site: TRIUMF-LCG2
  Month: 1
  Year: 2020
  GlobalUserName: None
  VO: atlas
  VOGroup: None
  VORole: None
  SubmitHost: boinc.lcg.triumf.ca
  InfrastructureType: grid
  ServiceLevelType: HEPSPEC
  ServiceLevel: 21.690
  NodeCount: 1
  Processors: 1
  %%
```
