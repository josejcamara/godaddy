#!/usr/bin/env python

""" GoDaddy domains managements via API"""

# pylint: disable=import-error, line-too-long, too-many-arguments, too-many-locals, too-many-nested-blocks, too-many-branches

import sys
import os
import argparse
import json
import urllib.parse
import tempfile
from time import sleep, time
import jsondiff as jd
import requests
from dotenv import load_dotenv

STATUS_OK = 200
STATUS_OK_DELETE = 204
STATUS_NOT_FOUND = 404
STATUS_TOO_MANY_REQUESTS = 429

#
#
#
def print_progress_bar(iteration, total, prefix='Progress:', suffix='Complete'):
    """ Progress Bar management """
    decimals = 1
    length = 50
    fill = '█'
    print_end = "\r"

    if total == 0:
        return

    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    pbar = fill * filled_length + '-' * (length - filled_length)
    suffix = suffix.ljust(100)
    print(f'\r{prefix} |{pbar}| {percent}% {suffix}', end=print_end)
    # Print New Line on Complete
    if iteration == total:
        print()

#
#
#
def call_api(action, action_call, data=None, dryrun=False, verbose=False, verify=True):
    """ Call to the API, adding the headers and returning a json object """

    api_key = os.getenv('GODADDY_API_KEY', None)
    secret_key = os.getenv('GODADDY_SECRET_KEY', None)
    godaddy_api_url = os.getenv('GODADDY_API_URL', 'https://api.ote-godaddy.com')

    if api_key is None:
        print('Not found env variable GODADDY_API_KEY')
        sys.exit(-1)
    if secret_key is None:
        print('Not found env variable GODADDY_SECRET_KEY')
        sys.exit(-1)

    api_url = godaddy_api_url
    if api_url.endswith('/'):
        api_url = api_url[:-1]
    if action_call.startswith('/'):
        action_call = action_call[1:]
    url_action = api_url + '/' + action_call

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f'sso-key {api_key}:{secret_key}'
    }

    if dryrun:
        print(' * dry_run * ', action, url_action, data)
        return (200, '* DRY RUN *')

    if verbose:
        print('>>>> REQUEST >>>>', url_action, data)

    response = requests.request(
        action,
        url_action,
        headers=headers,
        data=data,
        verify=verify
    )

    if verbose:
        print('<<<< RESPONSE <<<<', response.status_code, response.text)

    return (response.status_code, response.text)

#
#
#
def get_dns_records(domain_name, dns_types=None, verbose=False, verify=True):
    """ Return a list the dns types for a domain name """
    if verbose:
        print('Checking... ' + domain_name, dns_types)

    status, output = call_api('GET', f'v1/domains/{domain_name}/records', verbose=verbose, verify=verify)
    if status not in (STATUS_OK, STATUS_NOT_FOUND, STATUS_TOO_MANY_REQUESTS):
        print(f'ERROR: status {status}')
        sys.exit(-1)

    dns_details = json.loads(output)

    res = []

    if 'code' in dns_details:
        error_code = dns_details['code']
        if error_code == 'TOO_MANY_REQUESTS':
            print(f'\r{error_code} Waiting 30s...     ', end='\r')
            sleep(30)
            return get_dns_records(domain_name, dns_types)

        if error_code == 'UNKNOWN_DOMAIN':
            # This domain has not that dns type
            return None

        print('UNKNOWN ERROR CODE', dns_details)
        sys.exit(-1)
    else:
        if dns_types is None or len(dns_types) == 0:
            res = dns_details
        else:
            # Filter the requested dns_types
            for record in dns_details:
                if record['type'] in dns_types:
                    res.append(record)

    return res

#
#
#
def create_cloud_config_backup(dns_types, output_filename):
    """ Creates a json file as a backup for the goDaddy domains """
    res = {}

    status, output = call_api('GET', 'v1/domains?limit=999')
    if status != STATUS_OK:
        print(f'ERROR: status {status}')
        sys.exit(-1)
    my_domains = json.loads(output)

    if 'code' in my_domains:
        print('ERROR:', my_domains)
        sys.exit(-1)

    n_domains = len(my_domains)
    print_progress_bar(0, n_domains)
    for i, domain in enumerate(my_domains):
        domain_name = domain['domain']
        print_progress_bar(i + 1, n_domains, suffix='Complete - '+ domain_name)

        domain_dns = get_dns_records(domain_name, dns_types, verify=SSL_VERIFY, verbose=IS_VERBOSE)
        if domain_dns is not None and len(domain_dns) > 0:
            res[domain_name] = domain_dns

    if output_filename is not None:
        with open(output_filename, 'w', encoding="utf-8") as fp_out:
            json.dump(res, fp_out, indent=4)
    else:
        print(res)

    return res

#
#
#
def jd_update_to_dict(diff_map, state_cloud, state_desired):
    """ Converts the jsondiff output into a more useful dictionary for us to apply the cahnges """
    all_changes = {}
    # Changes in the domain's records
    for domain in diff_map:
        changes = all_changes.get(domain, {})
        for subaction in diff_map[domain]:
            if subaction == jd.insert:
                # New DNS record inserted
                for ddata in diff_map[domain][subaction]:
                    pos = ddata[0]
                    record = state_desired[domain][pos]
                    k_record = '/'.join([record['type'], record['name']])
                    changes[k_record] = []

            elif subaction == jd.delete:
                # DNS record deleted
                for pos in diff_map[domain][subaction]:
                    record = state_cloud[domain][pos]
                    k_record = '/'.join([record['type'], record['name']])
                    changes[k_record] = []

            elif isinstance(subaction, int):
                # DNS record updated
                pos = subaction
                for update_action in diff_map[domain][pos]:
                    if update_action in (jd.insert, jd.update):
                        record = state_desired[domain][pos]
                        k_record = '/'.join([record['type'], record['name']])
                        changes[k_record] = []  # Just for having the key. It will be populated in the Post action
                    else:
                        try:
                            record = state_cloud[domain][pos]
                        except IndexError:
                            print("WARNING!!!", update_action, domain, pos, state_cloud[domain])
                            record = {'type': 'None', 'name': 'None'}

                        k_record = '/'.join([record['type'], record['name']])
                        changes[k_record] = []

        # Post Action: Add all the records for the modified dns type/name
        for record in state_desired[domain]:
            k_record = '/'.join([record['type'], record['name']])
            if k_record in changes:
                changes[k_record].append(record)

        all_changes[domain] = changes

    return all_changes

#
#
#
def print_changes(all_changes, current):
    """ Shows the changes to apply and wait for confirmation """

    # Current formated to dict
    current_dc = {}
    for domain, dns_records in current.items():
        if not domain in current_dc:
            current_dc[domain] = {}
        for record in dns_records:
            k = (record['type'], record['name'])
            if not k in current_dc[domain]:
                current_dc[domain][k] = []
            current_dc[domain][k].append(record)

    # Table formated diff
    output_table = []
    for domain in all_changes:
        changes = all_changes[domain]
        original = current_dc.get(domain, {})
        for k_changes in changes:
            tmp_table = []
            tmp_table.append([domain, k_changes, '', ''])
            dns_records = changes[k_changes]
            original_records = original.get(tuple(k_changes.split('/')))
            if original_records is not None:
                for i, lns in enumerate(original_records):
                    if len(tmp_table) <= i:
                        tmp_table.append(['']*4)
                    tmp_table[i][2] = str(lns)

            for i, lns in enumerate(dns_records):
                if len(tmp_table) <= i:
                    tmp_table.append(['']*4)
                tmp_table[i][3] = str(lns)

            output_table.extend(tmp_table)
            output_table.append(['']*4)

    fmt_col = "{:<20} {:<20} {:<90} {:<90}"
    print(fmt_col.format('Domain', 'DNS Type/Name', 'Before', 'After'))
    print('-'*220)
    for lnt in output_table:
        print(fmt_col.format(lnt[0], lnt[1], str(lnt[2]), str(lnt[3])))

#
#
#
def get_cloud_config_differences(dns_types, source_filename, output_filename=None):
    """ Get the current goDaddy domains config, compares it with the source filename and apply changes if needed """
    temp_filename = os.path.join(tempfile.mkdtemp(), str(time()))
    print('\n#1. Getting cloud state...')
    create_cloud_config_backup(dns_types, temp_filename)
    state_cloud = None
    with open(temp_filename, 'r', encoding="utf-8") as f_temp:
        state_cloud = json.load(f_temp)
    os.remove(temp_filename)

    print(f'\n#2. Reading desired status file: {source_filename}')
    state_desired = None
    with open(source_filename, 'r', encoding="utf-8") as f_temp:
        state_desired = json.load(f_temp)

    print('\n#3. Checking differences...')
    diffs = jd.diff(state_cloud, state_desired, syntax='explicit')

    if diffs == {}:
        print('No changes found between cloud and source code')
        return

    # Group changes by domain
    for jd_action in diffs:
        if jd_action == jd.insert:
            # New domain inserted (do we need to cover this??)
            for domain in diffs[jd_action]:
                print('DOMAIN has to be added manually:', domain)

        elif jd_action == jd.delete:
            # Domain deleted (do we need to cover this??)
            for domain in diffs[jd_action]:
                print('DOMAIN has to be added manually:', domain)

        elif jd_action == jd.update:
            changes = jd_update_to_dict(diffs[jd_action], state_cloud, state_desired)
            print_changes(changes, state_cloud)

            if output_filename is not None:
                with open(output_filename, 'w', encoding="utf-8") as fp_out:
                    json.dump(changes, fp_out, indent=4)
                print(f'Plan saved in: {output_filename}')



def apply_cloud_config_differences(plan_filename):
    """ Having a plan file, it applies the changes into the cloud version """
    print('Applying changes...')

    changes = {}
    with open(plan_filename, 'r', encoding="utf-8") as fp_plan:
        changes = json.load(fp_plan)

    for domain, domain_changes in changes.items():
        for k_composed in domain_changes:
            k_type, k_name = k_composed.split('/')
            dns_records = domain_changes[k_composed]
            method_url = '/'.join(['v1', 'domains', domain, 'records', k_type, k_name])
            method_url = urllib.parse.quote(method_url)
            if dns_records == []:
                # Delete
                status, output = call_api('DELETE', method_url, dryrun=IS_DRYRUN, verify=SSL_VERIFY, verbose=IS_VERBOSE)
                if status != STATUS_OK_DELETE:
                    print('ERROR deleting', method_url, status, output)
            else:
                # Update
                status, output = call_api('PUT', method_url, data=json.dumps(dns_records), dryrun=IS_DRYRUN, verify=SSL_VERIFY, verbose=IS_VERBOSE)
                if status != STATUS_OK:
                    print('ERROR updating', method_url, status, output)

            print(k_composed, output)


#
#
#
def audit_no_route53_records(output_filename):
    """ It creates a json file with the settings on all the domains not using Route53 name servers and having MX or TXT dns_records """
    temp_filename = os.path.join(tempfile.mkdtemp(), str(time()))

    print('\n#1. Getting cloud state...')
    create_cloud_config_backup([], temp_filename)
    state_cloud = None
    with open(temp_filename, 'r', encoding="utf-8") as f_temp:
        state_cloud = json.load(f_temp)
    os.remove(temp_filename)

    print('\n#2. Checking nameservers...')
    domains_to_audit = {}
    for domain_name, dns_records in state_cloud.items():
        status, output = call_api('GET', f'v1/domains/{domain_name}', verify=SSL_VERIFY, verbose=IS_VERBOSE)
        if status not in (STATUS_OK, STATUS_NOT_FOUND, STATUS_TOO_MANY_REQUESTS):
            print(f'ERROR: status {status}')
            sys.exit(-1)

        output_json = json.loads(output)
        nameservers = output_json.get('nameServers', None)
        if nameservers is None:
            domains_to_audit[domain_name] = ['-- NO NAMESERVERS --', []]
            continue

        is_route53 = True
        for lnserver in nameservers:
            if '.awsdns-' not in lnserver:
                is_route53 = False
                break

        if not is_route53:
            dns_to_audit = []
            for ln_dns in dns_records:
                if ln_dns['type'] not in ('MX', 'TXT'):
                    # Out of interest for this audit
                    continue
                dns_to_audit.append(ln_dns)

            if len(dns_to_audit) > 0:
                domains_to_audit[domain_name] = [nameservers, dns_to_audit]

    print('\n#3. Saving results...')
    with open(output_filename, 'w', encoding="utf-8") as fp_out:
        json.dump(domains_to_audit, fp_out, indent=4)
        print(f'Created file {output_filename}')


#
#
#
def run(action):
    """ Run the script """

    records_type = CONFIG['records_type']
    dns_types = records_type.split(',') if records_type is not None else None

    # -- Actions
    if action == 'import':
        output_filename = 'godaddy_state.json' if CONFIG.get('output') is None else CONFIG['output']
        create_cloud_config_backup(dns_types, output_filename)

    elif action == 'plan':
        output_filename = 'godaddy_plan.json' if CONFIG.get('output') is None else CONFIG['output']
        state_filename = 'godaddy_state.json' if CONFIG['state'] is None else CONFIG['state']
        get_cloud_config_differences(dns_types, state_filename, output_filename)

    elif action == 'apply':
        plan_filename = 'godaddy_plan.json' if CONFIG['state'] is None else CONFIG['state']
        apply_cloud_config_differences(plan_filename)

    elif action == 'audit_r53':
        output_filename = 'godaddy_audit_r53.json' if CONFIG.get('output') is None else CONFIG['output']
        audit_no_route53_records(output_filename)

    else:
        print('Invalid action')

    print('\n--- Done ---\n')

def check_arguments():
    """ Check if tool arguments are rigth """
    action_list = ['import', 'plan', 'apply', 'audit_r53']

    parser = argparse.ArgumentParser(description="GoDaddy Management Tool", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("action", help="[ " + ' | '.join(action_list) + " ]")
    parser.add_argument("-e", "--environments", default='.env', type=str, help="Filename where to write the results ")
    parser.add_argument("-o", "--output", default=None, type=str, help="Filename where to write the results ")
    parser.add_argument("-s", "--state", default=None, type=str, help="Filename with the state information representing the desired status (plan/apply)")
    parser.add_argument("-t", "--records_type", type=str, help="Comma separated type of DNS records to perform the action to")
    parser.add_argument("--dry", action="store_true", help="Print out the actions to apply but without actually applying them")
    parser.add_argument("--no_verify", action="store_false", help="Disable security certificate checks. You may need this if using the Rapid7 agent")
    parser.add_argument("--verbose", action="store_true", help="Shows the requests calls information")

    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(-1)

    conf = vars(parser.parse_args())
    if not conf['action'] in action_list:
        print('Invalid value for "action". It should be any in', action_list)
        sys.exit(-1)

    return conf

#
# === MAIN ===
#
if __name__ == '__main__':

    CONFIG = check_arguments()

    IS_DRYRUN = CONFIG['dry']
    IS_VERBOSE = CONFIG['verbose']
    SSL_VERIFY = CONFIG['no_verify']

    load_dotenv(CONFIG['environments']) # Take environment variables from .env

    run(CONFIG['action'])
