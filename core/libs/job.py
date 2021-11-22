"""
Set of functions related to jobs metadata

Created by Tatiana Korchuganova on 05.03.2020
"""

import statistics
import json
import numpy as np
from core.libs.exlib import convert_bytes
from datetime import datetime, timedelta
from core.pandajob.models import Jobsactive4, Jobsarchived, Jobswaiting4, Jobsdefined4, Jobsarchived4
from core.libs.exlib import get_tmp_table_name, insert_to_temp_table, get_job_walltime, get_job_queuetime, \
    drop_duplicates, add_job_category

from core.ErrorCodes import ErrorCodes


def is_event_service(job):
    if 'eventservice' in job and job['eventservice'] is not None:
        if 'specialhandling' in job and job['specialhandling'] and (
                    job['specialhandling'].find('eventservice') >= 0 or job['specialhandling'].find('esmerge') >= 0 or (
                job['eventservice'] != 'ordinary' and job['eventservice'])) and job['specialhandling'].find('sc:') == -1:
                return True
        else:
            return False
    else:
        return False


def getErrorDescription(job, mode='html', provideProcessedCodes = False):
    txt = ''
    codesDescribed = []

    if 'metastruct' in job:
        if type(job['metastruct']) is np.unicode:
            try:
                meta = json.loads(job['metastruct'])
            except:
                print ('Meta type: '+str(type(job['metastruct'])))
                meta = job['metastruct']
            if 'exitCode' in meta and meta['exitCode'] != 0:
                txt += "%s: %s" % (meta['exitAcronym'], meta['exitMsg'])
                if provideProcessedCodes:
                    return txt, codesDescribed
                else:
                    return txt
            else:
                if provideProcessedCodes:
                    return '-', codesDescribed
                else:
                    return '-'
        else:
            meta = job['metastruct']
            if 'exitCode' in meta and meta['exitCode'] != 0:
                txt += "%s: %s" % (meta['exitAcronym'], meta['exitMsg'])
                if provideProcessedCodes:
                    return txt, codesDescribed
                else:
                    return txt

    codes = ErrorCodes()
    errorFields, errorCodes, errorStages = codes.getErrorCodes()

    for errcode in errorCodes.keys():
        errval = 0
        if errcode in job:
            errval = job[errcode]
            if errval != 0 and errval != '0' and errval != None and errval != '':
                try:
                    errval = int(errval)
                except:
                    pass  # errval = -1
                codesDescribed.append(errval)
                errdiag = errcode.replace('errorcode', 'errordiag')
                if errcode.find('errorcode') > 0:
                    if job[errdiag] is not None:
                        diagtxt = str(job[errdiag])
                    else:
                        diagtxt = ''
                else:
                    diagtxt = ''
                if len(diagtxt) > 0:
                    desc = diagtxt
                elif errval in errorCodes[errcode]:
                    desc = errorCodes[errcode][errval]
                else:
                    desc = "Unknown %s error code %s" % (errcode, errval)
                errname = errcode.replace('errorcode', '')
                errname = errname.replace('exitcode', '')
                if mode == 'html':
                    txt += " <b>%s, %d:</b> %s" % (errname, errval, desc)
                else:
                    txt = "%s, %d: %s" % (errname, errval, desc)
    if provideProcessedCodes:
        return txt, codesDescribed
    else:
        return txt


def errorInfo(job, nchars=300, mode='html'):
    errtxt = ''
    err1 = ''
    desc, codesDescribed = getErrorDescription(job, provideProcessedCodes=True)

    if 'brokerageerrorcode' in job and int(job['brokerageerrorcode']) != 0 and int(job['brokerageerrorcode']) not in codesDescribed:
        errtxt += 'Brokerage error %s: %s <br>' % (job['brokerageerrorcode'], job['brokerageerrordiag'])
        if err1 == '': err1 = "Broker: %s" % job['brokerageerrordiag']
    if 'ddmerrorcode' in job and int(job['ddmerrorcode']) != 0 and int(job['ddmerrorcode']) not in codesDescribed:
        errtxt += 'DDM error %s: %s <br>' % (job['ddmerrorcode'], job['ddmerrordiag'])
        if err1 == '': err1 = "DDM: %s" % job['ddmerrordiag']
    if 'exeerrorcode' in job and int(job['exeerrorcode']) != 0 and int(job['exeerrorcode']) not in codesDescribed:
        errtxt += 'Executable error %s: %s <br>' % (job['exeerrorcode'], job['exeerrordiag'])
        if err1 == '': err1 = "Exe: %s" % job['exeerrordiag']
    if 'jobdispatchererrorcode' in job and int(job['jobdispatchererrorcode']) != 0 and int(job['jobdispatchererrorcode']) not in codesDescribed:
        errtxt += 'Dispatcher error %s: %s <br>' % (job['jobdispatchererrorcode'], job['jobdispatchererrordiag'])
        if err1 == '': err1 = "Dispatcher: %s" % job['jobdispatchererrordiag']
    if 'piloterrorcode' in job and int(job['piloterrorcode']) != 0 and int(job['piloterrorcode']) not in codesDescribed:
        errtxt += 'Pilot error %s: %s <br>' % (job['piloterrorcode'], job['piloterrordiag'])
        if err1 == '': err1 = "Pilot: %s" % job['piloterrordiag']
    if 'superrorcode' in job and int(job['superrorcode']) != 0 and int(job['superrorcode']) not in codesDescribed:
        errtxt += 'Sup error %s: %s <br>' % (job['superrorcode'], job['superrordiag'])
        if err1 == '': err1 = job['superrordiag']
    if 'taskbuffererrorcode' in job and int(job['taskbuffererrorcode']) != 0 and int(job['taskbuffererrorcode']) not in codesDescribed:
        errtxt += 'Task buffer error %s: %s <br>' % (job['taskbuffererrorcode'], job['taskbuffererrordiag'])
        if err1 == '': err1 = 'Taskbuffer: %s' % job['taskbuffererrordiag']
    if 'transexitcode' in job and job['transexitcode'] != '' and job['transexitcode'] is not None and int(job['transexitcode']) > 0 and int(job['transexitcode']) not in codesDescribed:
        errtxt += 'Trf exit code %s.' % job['transexitcode']
        if err1 == '': err1 = 'Trf exit code %s' % job['transexitcode']
    if len(desc) > 0:
        errtxt += '%s<br>' % desc
        if err1 == '': err1 = getErrorDescription(job, mode='string')
    if len(errtxt) > nchars:
        ret = errtxt[:nchars] + '...'
    else:
        ret = errtxt[:nchars]
    if err1.find('lost heartbeat') >= 0: err1 = 'lost heartbeat'
    if err1.lower().find('unknown transexitcode') >= 0: err1 = 'unknown transexit'
    if err1.find(' at ') >= 0: err1 = err1[:err1.find(' at ') - 1]
    if errtxt.find('lost heartbeat') >= 0: err1 = 'lost heartbeat'
    err1 = err1.replace('\n', ' ')

    if mode == 'html':
        return errtxt
    else:
        return err1[:nchars]


def get_job_list(query, **kwargs):

    MAX_ENTRIES__IN = 100

    jobs = []
    values = [
        'actualcorecount', 'eventservice', 'specialhandling', 'modificationtime', 'jobsubstatus', 'pandaid',
        'jobstatus', 'jeditaskid', 'processingtype', 'maxpss', 'starttime', 'endtime', 'computingsite',
        'jobsetid', 'jobmetrics', 'nevents', 'hs06', 'hs06sec', 'cpuconsumptiontime', 'parentid', 'attemptnr',
        'processingtype', 'transformation', 'creationtime', 'diskio'
    ]
    if 'values' in kwargs:
        values.extend(kwargs['values'])
        values = set(values)

    extra_str = "(1=1)"
    if 'extra_str' in kwargs and kwargs['extra_str'] != '':
        extra_str = kwargs['extra_str']

    if 'jeditaskid__in' in query and len(query['jeditaskid__in']) > MAX_ENTRIES__IN:
        # insert taskids to temp DB table
        tmp_table_name = get_tmp_table_name()
        tk_taskids = insert_to_temp_table(query['jeditaskid__in'])
        extra_str += " AND jeditaskid in (select ID from {} where TRANSACTIONKEY={})".format(tmp_table_name, tk_taskids)
        del query['jeditaskid__in']

    jobs.extend(Jobsdefined4.objects.filter(**query).extra(where=[extra_str]).values(*values))
    jobs.extend(Jobswaiting4.objects.filter(**query).extra(where=[extra_str]).values(*values))
    jobs.extend(Jobsactive4.objects.filter(**query).extra(where=[extra_str]).values(*values))
    jobs.extend(Jobsarchived4.objects.filter(**query).extra(where=[extra_str]).values(*values))

    if 'jeditaskid' in query or 'jeditaskid__in' in query or 'jeditaskid' in extra_str or (
        'modificationtime__castdate__range' in query and query['modificationtime__castdate__range'][0] < (
            datetime.now() - timedelta(days=3))) or (len(jobs) == 0 and 'pandaid' in query):
        jobs.extend(Jobsarchived.objects.filter(**query).extra(where=[extra_str]).values(*values))

    # drop duplicate jobs
    jobs = drop_duplicates(jobs, id='pandaid')

    # add job category
    jobs = add_job_category(jobs)

    return jobs


def parse_jobmetrics(jobs):
    """
    Parse and add the metrics to job dicts
    :param jobs: list
    :return: jobs
    """
    for job in jobs:
        if 'jobmetrics' in job and job['jobmetrics'] and len(job['jobmetrics']) > 0:
            jobmetrics = {str(jm.split('=')[0]).lower(): jm.split('=')[1] for jm in job['jobmetrics'].split(' ')}
            if 'actualcorecount' in jobmetrics:
                jobmetrics['nprocesses'] = jobmetrics['actualcorecount']
                del jobmetrics['actualcorecount']
            for jm in jobmetrics:
                try:
                    jobmetrics[jm] = float(jobmetrics[jm])
                except:
                    pass
            job.update(jobmetrics)

    return jobs


def calc_jobs_metrics(jobs, group_by='jeditaskid'):
    """
    Calculate interesting metrics, e.g. avg maxpss/core, avg job walltime, avg job queuetime, failedpct
    :param jobs: list of dicts
    :param group_by:
    :return metrics_dict: dict
    """
    metrics_dict = {
        'maxpss_per_actualcorecount': {'total': [], 'group_by': {}, 'agg': 'median'},
        'diskio': {'total': [], 'group_by': {}, 'agg': 'median'},
        'walltime': {'total': [], 'group_by': {}, 'agg': 'median'},
        'queuetime': {'total': [], 'group_by': {}, 'agg': 'median'},
        'failed': {'total': [], 'group_by': {}, 'agg': 'average'},
        'efficiency': {'total': [], 'group_by': {}, 'agg': 'median'},
        'attemptnr': {'total': [], 'group_by': {}, 'agg': 'average'},
        'walltime_loss': {'total': [], 'group_by': {}, 'agg': 'sum'},
        'cputime_loss': {'total': [], 'group_by': {}, 'agg': 'sum'},
    }

    # calc metrics
    for job in jobs:
        if group_by in job and job[group_by]:

            job['failed'] = 100 if 'jobstatus' in job and job['jobstatus'] == 'failed' else 0
            job['attemptnr'] = job['attemptnr'] + 1

            if job['category'] == 'run':
                if 'maxpss' in job and job['maxpss'] and isinstance(job['maxpss'], int) and (
                        'actualcorecount' in job and isinstance(job['actualcorecount'], int) and job['actualcorecount'] > 0):
                    job['maxpss_per_actualcorecount'] = convert_bytes(1.0*job['maxpss']/job['actualcorecount'], output_unit='MB')

                job['diskio'] = job['diskio'] if 'diskio' in job and job['diskio'] is not None else 0

                job['walltime'] = get_job_walltime(job)
                job['queuetime'] = get_job_queuetime(job)

                if job['walltime'] and 'cpuconsumptiontime' in job and (
                        isinstance(job['cpuconsumptiontime'], int) and job['cpuconsumptiontime'] > 0) and (
                        'actualcorecount' in job and isinstance(job['actualcorecount'], int) and job['actualcorecount'] > 0):
                    job['efficiency'] = round(1.0*job['cpuconsumptiontime']/job['walltime']/job['actualcorecount'], 2)

                job['cputime'] = round(job['cpuconsumptiontime'] / 60. / 60., 2) if 'cpuconsumptiontime' in job and isinstance(job['cpuconsumptiontime'], int) else 0

                job['walltime'] = round(job['walltime'] / 60. / 60., 2) if job['walltime'] is not None else 0
                job['queuetime'] = round(job['queuetime'] / 60. / 60., 2) if job['queuetime'] is not None else 0

                job['walltime_loss'] = job['walltime'] if 'jobstatus' in job and job['jobstatus'] == 'failed' else 0
                job['cputime_loss'] = job['cputime'] if 'jobstatus' in job and job['jobstatus'] == 'failed' else 0

            for metric in metrics_dict:
                if metric in job and job[metric] is not None:
                    if job[group_by] not in metrics_dict[metric]['group_by']:
                        metrics_dict[metric]['group_by'][job[group_by]] = []
                    metrics_dict[metric]['group_by'][job[group_by]].append(job[metric])
                    metrics_dict[metric]['total'].append(job[metric])

    for metric in metrics_dict:
        if len(metrics_dict[metric]['total']) > 0:
            if metrics_dict[metric]['agg'] == 'median':
                metrics_dict[metric]['total'] = round(statistics.median(metrics_dict[metric]['total']), 2)
            elif metrics_dict[metric]['agg'] == 'average':
                metrics_dict[metric]['total'] = round(statistics.mean(metrics_dict[metric]['total']), 2)
        else:
            metrics_dict[metric]['total'] = -1
        for gbp in metrics_dict[metric]['group_by']:
            if len(metrics_dict[metric]['group_by'][gbp]) > 0:
                if metrics_dict[metric]['agg'] == 'median':
                    metrics_dict[metric]['group_by'][gbp] = round(statistics.median(metrics_dict[metric]['group_by'][gbp]), 2)
                elif metrics_dict[metric]['agg'] == 'average':
                    metrics_dict[metric]['group_by'][gbp] = round(statistics.mean(metrics_dict[metric]['group_by'][gbp]), 2)
            else:
                metrics_dict[metric]['group_by'][gbp] = -1

    return metrics_dict


def get_job_errors(pandaids):
    """
    Get error info for a list of PanDA jobs
    :param pandaids: list of pandaids
    :return: errors_dict: dict
    """
    MAX_ENTRIES__IN = 100

    errors_dict = {}

    jobs = []
    jquery = {}
    extra_str = ' (1=1) '
    values = (
        'pandaid',
        'transexitcode',
        'brokerageerrorcode', 'brokerageerrordiag',
        'ddmerrorcode', 'ddmerrordiag',
        'exeerrorcode', 'exeerrordiag',
        'jobdispatchererrorcode', 'jobdispatchererrordiag',
        'piloterrorcode', 'piloterrordiag',
        # 'superrorcode', 'superrordiag',
        'taskbuffererrorcode', 'taskbuffererrordiag'
        )

    if len(pandaids) > 0 and len(pandaids) <= MAX_ENTRIES__IN:
        jquery['pandaid__in'] = pandaids
    elif len(pandaids) > 0 and len(pandaids) > MAX_ENTRIES__IN:
        # insert pandaids to temp DB table
        tmp_table_name = get_tmp_table_name()
        tk_pandaids = insert_to_temp_table(pandaids)
        extra_str += " AND pandaid in (select ID from {} where TRANSACTIONKEY={})".format(tmp_table_name, tk_pandaids)
    else:
        return errors_dict

    jobs.extend(Jobsarchived4.objects.filter(**jquery).extra(where=[extra_str]).values(*values))
    jobs.extend(Jobsarchived.objects.filter(**jquery).extra(where=[extra_str]).values(*values))

    for job in jobs:
        errors_dict[job['pandaid']] = errorInfo(job)

    return errors_dict
