"""

"""
import logging
import copy
from datetime import datetime, timedelta

from django.db import connection
from django.db.models import Q, Count, Sum

from core.harvester.models import HarvesterWorkerStats, HarvesterWorkers
from core.pandajob.models import PandaJob

from core.schedresource.utils import get_panda_queues

from core.settings.local import defaultDatetimeFormat

_logger = logging.getLogger('bigpandamon')

job_states_order = [
    'pending', 'defined', 'waiting', 'assigned', 'throttled',
    'activated', 'sent', 'starting', 'running', 'holding',
    'transferring', 'merging', 'finished', 'failed', 'cancelled', 'closed']


def prepare_job_summary_region(jsr_queues_dict, jsr_regions_dict, **kwargs):
    """
    Convert dict of region job summary to list
    :param dict of region job summary, dict of queue job summary
    :return: list of region job summary, list of queue job summary
    """
    split_by = None
    if 'split_by' in kwargs and kwargs['split_by']:
        split_by = kwargs['split_by']
    jsr_queues_list = []
    jsr_regions_list = []
    for pq, params in jsr_queues_dict.items():
        for jt, resourcetypes in params['summary'].items():
            for rt, summary in resourcetypes.items():
                if sum([v for k, v in summary.items() if k in job_states_order]) > 0:  # filter out rows with 0 jobs
                    row = list()
                    row.append(pq)
                    row.append(params['pq_params']['pqtype'])
                    row.append(params['pq_params']['region'])
                    row.append(params['pq_params']['status'])
                    row.append(jt)
                    row.append(rt)
                    row.append(summary['nwsubmitted'])
                    row.append(summary['nwrunning'])
                    row.append(summary['rcores'])
                    row.append(sum([v for k, v in summary.items() if k in job_states_order]))
                    if summary['failed'] + summary['finished'] > 0:
                        row.append(round(100.0*summary['failed']/(summary['failed'] + summary['finished']), 1))
                    else:
                        row.append(0)
                    for js in job_states_order:
                        row.append(summary[js])

                    if split_by is None:
                        if jt == 'all' and rt == 'all':
                            jsr_queues_list.append(row)
                    elif 'jobtype' in split_by and 'resourcetype' in split_by:
                        if jt != 'all' and rt != 'all':
                            jsr_queues_list.append(row)
                    elif 'jobtype' in split_by and 'resourcetype' not in split_by:
                        if jt != 'all' and rt == 'all':
                            jsr_queues_list.append(row)
                    elif 'jobtype' not in split_by and 'resourcetype' in split_by:
                        if jt == 'all' and rt != 'all':
                            jsr_queues_list.append(row)

    for reg, jobtypes in jsr_regions_dict.items():
        for jt, resourcetypes in jobtypes.items():
            for rt, summary in resourcetypes.items():
                if sum([v for k, v in summary.items() if k in job_states_order]) > 0:  # filter out rows with 0 jobs
                    row = list()
                    row.append(reg)
                    row.append(jt)
                    row.append(rt)
                    row.append(summary['nwsubmitted'])
                    row.append(summary['nwrunning'])
                    row.append(summary['rcores'])
                    row.append(sum([v for k, v in summary.items() if k in job_states_order]))
                    if summary['failed'] + summary['finished'] > 0:
                        row.append(round(100.0 * summary['failed'] / (summary['failed'] + summary['finished']), 1))
                    else:
                        row.append(0)
                    for js in job_states_order:
                        row.append(summary[js])

                    if split_by is None:
                        if jt == 'all' and rt == 'all':
                            jsr_regions_list.append(row)
                    elif 'jobtype' in split_by and 'resourcetype' in split_by:
                        if jt != 'all' and rt != 'all':
                            jsr_regions_list.append(row)
                    elif 'jobtype' in split_by and 'resourcetype' not in split_by:
                        if jt != 'all' and rt == 'all':
                            jsr_regions_list.append(row)
                    elif 'jobtype' not in split_by and 'resourcetype' in split_by:
                        if jt == 'all' and rt != 'all':
                            jsr_regions_list.append(row)
    return jsr_queues_list, jsr_regions_list


def get_job_summary_region(query, job_states_order, extra='(1=1)'):
    """
    :param query: dict of query params for jobs retrieving
    :return: dict of groupings
    """
    jsr_queues_dict = {}
    jsr_regions_dict = {}

    job_types = ['analy', 'prod']
    resource_types = ['SCORE', 'MCORE', 'SCORE_HIMEM', 'MCORE_HIMEM']
    worker_metrics = ['nwrunning', 'nwsubmitted']
    extra_metrics = copy.deepcopy(worker_metrics)
    extra_metrics.append('rcores')

    # get PQ info
    panda_queues_dict = get_panda_queues()

    regions_list = list(set([params['cloud'] for pq, params in panda_queues_dict.items()]))

    # filter out queues by queue related selection params
    pq_to_remove = []
    if 'queuestatus' in query:
        pq_to_remove.extend([pqn for pqn, params in panda_queues_dict.items() if params['status'] != query['queuestatus']])
    if 'queuetype' in query:
        pq_to_remove.extend([pqn for pqn, params in panda_queues_dict.items() if params['type'] != query['queuetype']])
    if len(pq_to_remove) > 0:
        for pqr in list(set(pq_to_remove)):
            del panda_queues_dict[pqr]

    # create template structure for grouping by queue
    for pqn, params in panda_queues_dict.items():
        jsr_queues_dict[pqn] = {'pq_params': {}, 'summary': {}}
        jsr_queues_dict[pqn]['pq_params']['pqtype'] = params['type']
        jsr_queues_dict[pqn]['pq_params']['region'] = params['cloud']
        jsr_queues_dict[pqn]['pq_params']['status'] = params['status']
        for jt in job_types:
            jsr_queues_dict[pqn]['summary'][jt] = {}
            jsr_queues_dict[pqn]['summary']['all'] = {}
            for rt in resource_types:
                jsr_queues_dict[pqn]['summary'][jt][rt] = {}
                jsr_queues_dict[pqn]['summary'][jt]['all'] = {}
                jsr_queues_dict[pqn]['summary']['all'][rt] = {}
                jsr_queues_dict[pqn]['summary']['all']['all'] = {}
                for js in job_states_order:
                    jsr_queues_dict[pqn]['summary'][jt][rt][js] = 0
                    jsr_queues_dict[pqn]['summary'][jt]['all'][js] = 0
                    jsr_queues_dict[pqn]['summary']['all'][rt][js] = 0
                    jsr_queues_dict[pqn]['summary']['all']['all'][js] = 0

                for em in extra_metrics:
                    jsr_queues_dict[pqn]['summary'][jt][rt][em] = 0
                    jsr_queues_dict[pqn]['summary'][jt]['all'][em] = 0
                    jsr_queues_dict[pqn]['summary']['all'][rt][em] = 0
                    jsr_queues_dict[pqn]['summary']['all']['all'][em] = 0



    # create template structure for grouping by region
    for r in regions_list:
        jsr_regions_dict[r] = {}
        for jt in job_types:
            jsr_regions_dict[r][jt] = {}
            jsr_regions_dict[r]['all'] = {}
            for rt in resource_types:
                jsr_regions_dict[r][jt][rt] = {}
                jsr_regions_dict[r][jt]['all'] = {}
                jsr_regions_dict[r]['all'][rt] = {}
                jsr_regions_dict[r]['all']['all'] = {}
                for js in job_states_order:
                    jsr_regions_dict[r][jt][rt][js] = 0
                    jsr_regions_dict[r][jt]['all'][js] = 0
                    jsr_regions_dict[r]['all'][rt][js] = 0
                    jsr_regions_dict[r]['all']['all'][js] = 0

                for em in extra_metrics:
                    jsr_regions_dict[r][jt][rt][em] = 0
                    jsr_regions_dict[r][jt]['all'][em] = 0
                    jsr_regions_dict[r]['all'][rt][em] = 0
                    jsr_regions_dict[r]['all']['all'][em] = 0

    # get job info
    jsq = get_job_summary_split(query, extra=extra)

    # get workers info
    if 'computingsite__in' not in query:
        # put full list of compitingsites to use index in workers table
        query['computingsite__in'] = list(set([row['computingsite'] for row in jsq]))
    wsq = get_workers_summary_split(query)

    # fill template with real values of job states counts
    for row in jsq:
        if row['computingsite'] in jsr_queues_dict and row['jobtype'] in job_types and row['resourcetype'] in resource_types and row['jobstatus'] in job_states_order and 'count' in row:
            jsr_queues_dict[row['computingsite']]['summary'][row['jobtype']][row['resourcetype']][row['jobstatus']] += int(row['count'])
            jsr_queues_dict[row['computingsite']]['summary']['all'][row['resourcetype']][row['jobstatus']] += int(row['count'])
            jsr_queues_dict[row['computingsite']]['summary'][row['jobtype']]['all'][row['jobstatus']] += int(row['count'])
            jsr_queues_dict[row['computingsite']]['summary']['all']['all'][row['jobstatus']] += int(row['count'])

            jsr_regions_dict[jsr_queues_dict[row['computingsite']]['pq_params']['region']][row['jobtype']][row['resourcetype']][row['jobstatus']] += int(row['count'])
            jsr_regions_dict[jsr_queues_dict[row['computingsite']]['pq_params']['region']]['all'][row['resourcetype']][row['jobstatus']] += int(row['count'])
            jsr_regions_dict[jsr_queues_dict[row['computingsite']]['pq_params']['region']][row['jobtype']]['all'][row['jobstatus']] += int(row['count'])
            jsr_regions_dict[jsr_queues_dict[row['computingsite']]['pq_params']['region']]['all']['all'][row['jobstatus']] += int(row['count'])

            # fill sum of running cores
            if row['jobstatus'] == 'running':
                jsr_queues_dict[row['computingsite']]['summary'][row['jobtype']][row['resourcetype']]['rcores'] += int(row['rcores'])
                jsr_queues_dict[row['computingsite']]['summary']['all'][row['resourcetype']]['rcores'] += int(row['rcores'])
                jsr_queues_dict[row['computingsite']]['summary'][row['jobtype']]['all']['rcores'] += int(row['rcores'])
                jsr_queues_dict[row['computingsite']]['summary']['all']['all']['rcores'] += int(row['rcores'])

                jsr_regions_dict[jsr_queues_dict[row['computingsite']]['pq_params']['region']][row['jobtype']][row['resourcetype']]['rcores'] += int(row['rcores'])
                jsr_regions_dict[jsr_queues_dict[row['computingsite']]['pq_params']['region']]['all'][row['resourcetype']]['rcores'] += int(row['rcores'])
                jsr_regions_dict[jsr_queues_dict[row['computingsite']]['pq_params']['region']][row['jobtype']]['all']['rcores'] += int(row['rcores'])
                jsr_regions_dict[jsr_queues_dict[row['computingsite']]['pq_params']['region']]['all']['all']['rcores'] += int(row['rcores'])

    # fill template with real values of n workers stats
    for row in wsq:
        if row['computingsite'] in jsr_queues_dict and row['jobtype'] in job_types and row['resourcetype'] in resource_types:
            for wm in worker_metrics:
                jsr_queues_dict[row['computingsite']]['summary'][row['jobtype']][row['resourcetype']][wm] += int(row[wm])
                jsr_queues_dict[row['computingsite']]['summary']['all'][row['resourcetype']][wm] += int(row[wm])
                jsr_queues_dict[row['computingsite']]['summary'][row['jobtype']]['all'][wm] += int(row[wm])
                jsr_queues_dict[row['computingsite']]['summary']['all']['all'][wm] += int(row[wm])

                jsr_regions_dict[jsr_queues_dict[row['computingsite']]['pq_params']['region']][row['jobtype']][row['resourcetype']][wm] += int(row[wm])
                jsr_regions_dict[jsr_queues_dict[row['computingsite']]['pq_params']['region']]['all'][row['resourcetype']][wm] += int(row[wm])
                jsr_regions_dict[jsr_queues_dict[row['computingsite']]['pq_params']['region']][row['jobtype']]['all'][wm] += int(row[wm])
                jsr_regions_dict[jsr_queues_dict[row['computingsite']]['pq_params']['region']]['all']['all'][wm] += int(row[wm])

    return jsr_queues_dict, jsr_regions_dict


def get_job_summary_split(query, extra):
    """ Query the jobs summary """
    fields = {field.attname: field.db_column for field in PandaJob._meta.get_fields()}
    extra_str = extra
    for qn, qvs in query.items():
        if '__in' in qn and qn.replace('__in', '') in fields:
            extra_str += " and (" + fields[qn.replace('__in', '')] + " in ("
            for qv in qvs:
                extra_str += "'" + str(qv) + "',"
            extra_str = extra_str[:-1]
            extra_str += "))"
        elif '__icontains' in qn or '__contains' in qn and qn.replace('__icontains', '').replace('__contains', '') in fields:
            extra_str += " and (" + fields[qn.replace('__icontains', '').replace('__contains', '')] + " LIKE '%%" + qvs + "%%')"
        elif qn in fields:
            extra_str += " and (" + fields[qn] + "= '" + qvs + "' )"

    # get jobs groupings, the jobsactive4 table can keep failed analysis jobs for up to 7 days, so splitting the query
    query_raw = """
        select computingsite, resource_type as resourcetype, prodsourcelabel, jobstatus, 
            count(pandaid) as count, sum(rcores) as rcores, round(sum(walltime)) as walltime
        from  (
        select ja4.pandaid, ja4.resource_type, ja4.computingsite, ja4.prodsourcelabel, ja4.jobstatus, ja4.modificationtime, 0 as rcores,
            case when jobstatus in ('finished', 'failed') then (ja4.endtime-ja4.starttime)*60*60*24 else 0 end as walltime
        from ATLAS_PANDA.JOBSARCHIVED4 ja4  where modificationtime > TO_DATE('{0}', 'YYYY-MM-DD HH24:MI:SS') and {1}
        union
        select jav4.pandaid, jav4.resource_type, jav4.computingsite, jav4.prodsourcelabel, jav4.jobstatus, jav4.modificationtime,
        case when jobstatus = 'running' then actualcorecount else 0 end as rcores, 0 as walltime
        from ATLAS_PANDA.jobsactive4 jav4 where modificationtime > TO_DATE('{0}', 'YYYY-MM-DD HH24:MI:SS') and 
            jobstatus in ('failed', 'finished', 'closed', 'cancelled') and {1}
        union
        select jav4.pandaid, jav4.resource_type, jav4.computingsite, jav4.prodsourcelabel, jav4.jobstatus, jav4.modificationtime,
        case when jobstatus = 'running' then actualcorecount else 0 end as rcores, 0 as walltime
        from ATLAS_PANDA.jobsactive4 jav4 where jobstatus not in ('failed', 'finished', 'closed', 'cancelled') and {1}
        union
        select jw4.pandaid, jw4.resource_type, jw4.computingsite, jw4.prodsourcelabel, jw4.jobstatus, jw4.modificationtime, 0 as rcores, 0 as walltime
        from ATLAS_PANDA.jobswaiting4 jw4 where {1}
        union
        select jd4.pandaid, jd4.resource_type, jd4.computingsite, jd4.prodsourcelabel, jd4.jobstatus, jd4.modificationtime, 0 as rcores, 0 as walltime
        from ATLAS_PANDA.jobsdefined4 jd4  where {1}
        )
        GROUP BY computingsite, prodsourcelabel, resource_type, jobstatus
        order by computingsite, prodsourcelabel, resource_type, jobstatus
    """.format(query['modificationtime__castdate__range'][0], extra_str)

    cur = connection.cursor()
    cur.execute(query_raw)
    job_summary_tuple = cur.fetchall()
    job_summary_header = ['computingsite', 'resourcetype', 'prodsourcelabel', 'jobstatus', 'count', 'rcores', 'walltime']
    summary = [dict(zip(job_summary_header, row)) for row in job_summary_tuple]

    # Translate prodsourcelabel values to descriptive analy|prod job types
    summary = prodsourcelabel_to_jobtype(summary)

    return summary


def get_workers_summary_split(query, **kwargs):
    """Get statistics of submitted and running Harvester workers"""
    N_HOURS = 100
    wquery = {}
    if 'computingsite__in' in query:
        wquery['computingsite__in'] = query['computingsite__in']
    if 'resourcetype' in query:
        wquery['resourcetype'] = query['resourcetype']

    if 'source' in kwargs and kwargs['source'] == 'HarvesterWorkers':
        wquery['submittime__castdate__range'] = [
            (datetime.utcnow()-timedelta(hours=N_HOURS)).strftime(defaultDatetimeFormat),
            datetime.utcnow().strftime(defaultDatetimeFormat)
        ]
        wquery['status__in'] = ['running', 'submitted']
        # wquery['jobtype__in'] = ['managed', 'user', 'panda']
        w_running = Count('jobtype', filter=Q(status__exact='running'))
        w_submitted = Count('jobtype', filter=Q(status__exact='submitted'))
        w_values = ['computingsite', 'resourcetype', 'jobtype']
        worker_summary = HarvesterWorkers.objects.filter(**wquery).values(*w_values).annotate(nwrunning=w_running).annotate(nwsubmitted=w_submitted)
    else:
        wquery['jobtype__in'] = ['managed', 'user', 'panda']
        w_running = Sum('nworkers', filter=Q(status__exact='running'))
        w_submitted = Sum('nworkers', filter=Q(status__exact='submitted'))
        w_values = ['computingsite', 'resourcetype', 'jobtype']
        worker_summary = HarvesterWorkerStats.objects.filter(**wquery).values(*w_values).annotate(nwrunning=w_running).annotate(nwsubmitted=w_submitted)

    # Translate prodsourcelabel values to descriptive analy|prod job types
    worker_summary = prodsourcelabel_to_jobtype(worker_summary, field_name='jobtype')

    return list(worker_summary)


def prodsourcelabel_to_jobtype(list_of_dict, field_name='prodsourcelabel'):
    """Translate prodsourcelabel values to descriptive analy|prod job types"""

    psl_to_jt = {
        'panda': 'analy',
        'user': 'analy',
        'managed': 'prod',
        'prod_test': 'prod',
        'ptest': 'prod',
        'rc_alrb': 'prod',
        'rc_test2': 'prod',
    }
    new_list_of_dict = []
    for row in list_of_dict:
        if field_name in row and row[field_name] in psl_to_jt.keys():
            row['jobtype'] = psl_to_jt[row[field_name]]
            new_list_of_dict.append(row)

    return new_list_of_dict


def prettify_json_output(jsr_queues_dict, jsr_regions_dict, **kwargs):
    """
    Remove queues|regions with 0 jobs, add links to jobs page if requested
    :param jsr_queues_dict:
    :param jsr_regions_dict:
    :return:
    """
    region_summary = {}
    queue_summary = {}

    is_add_link = False
    if 'extra' in kwargs and 'links' in kwargs['extra'] and kwargs['extra']['links'] is True:
        is_add_link = True
    if 'hours' in kwargs:
        hours = kwargs['hours']
    else:
        hours = 12

    base_url = 'https://bigpanda.cern.ch'
    jobs_path = '/jobs/?hours=' + str(hours)

    for rn, rdict in jsr_regions_dict.items():
        for jt, jtdict in rdict.items():
            for rt, rtdict in jtdict.items():
                if sum([rtdict[js] for js in job_states_order if js in rtdict]) > 0:
                    if rn not in region_summary:
                        region_summary[rn] = {}
                    if jt not in region_summary[rn]:
                        region_summary[rn][jt] = {}
                    if rt not in region_summary[rn][jt]:
                        region_summary[rn][jt][rt] = []
                    for js in job_states_order:
                        temp_dict = {
                            'jobstatus': js,
                            'count': rtdict[js]
                        }
                        if is_add_link:
                            temp_dict['job_link'] = base_url + jobs_path + '&region=' + rn + '&jobstatus=' + js
                            if jt != 'all':
                                temp_dict['job_link'] += '&jobtype=' + jt
                            if rt != 'all':
                                temp_dict['job_link'] += '&resourcetype=' + rt
                        region_summary[rn][jt][rt].append(temp_dict)

    for qn, qdict in jsr_queues_dict.items():
        for jt, jtdict in qdict['summary'].items():
            for rt, rtdict in jtdict.items():
                if sum([rtdict[js] for js in job_states_order if js in rtdict]) > 0:
                    if qn not in queue_summary:
                        queue_summary[qn] = qdict['pq_params']
                        queue_summary[qn]['job_summary'] = {}
                    if jt not in queue_summary[qn]['job_summary']:
                        queue_summary[qn]['job_summary'][jt] = {}
                    if rt not in queue_summary[qn]['job_summary'][jt]:
                        queue_summary[qn]['job_summary'][jt][rt] = []
                    for js in job_states_order:
                        temp_dict = {
                            'jobstatus': js,
                            'count': rtdict[js]
                        }
                        if is_add_link:
                            temp_dict['job_link'] = base_url + jobs_path + '&computingsite=' + qn + '&jobstatus=' + js
                            if jt != 'all':
                                temp_dict['job_link'] += '&jobtype=' + jt
                            if rt != 'all':
                                temp_dict['job_link'] += '&resourcetype=' + rt
                        queue_summary[qn]['job_summary'][jt][rt].append(temp_dict)

    return queue_summary, region_summary