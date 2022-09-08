import sys
import os
import argparse
import json
from tabnanny import verbose
import requests
from dotenv import load_dotenv
from time import sleep, time
import tempfile
import jsondiff as jd
import urllib.parse

STATUS_OK = 200
STATUS_OK_DELETE = 204
STATUS_NOT_FOUND = 404
STATUS_TOO_MANY_REQUESTS = 429

#
#
#
def printProgressBar (iteration, total, prefix = 'Progress:', suffix = 'Complete', decimals = 1, length = 50, fill = '█', printEnd = "\r"):
    if total == 0:
        return

    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    suffix = suffix.ljust(100)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()
        # print(f'\r' + 150*'', end = printEnd)  # Clean the progress bar line

#
#
#
def call_api(op, action, data=None, dryrun=False, verbose=False):
    """ Call to the API, adding the headers and returning a json object """

    API_KEY = os.getenv('GODADDY_API_KEY_'+scope, None)
    SECRET_KEY = os.getenv('GODADDY_SECRET_KEY_'+scope, None)
    GODADDY_API_URL=os.getenv('GODADDY_API_URL', 'https://api.ote-godaddy.com')

    if API_KEY == None:
        print('Not found env variable GODADDY_API_KEY_'+scope)
        exit(-1)
    if SECRET_KEY == None:
        print('Not found env variable GODADDY_SECRET_KEY_'+scope)
        exit(-1)

    api_url = GODADDY_API_URL
    if api_url.endswith('/'):
        api_url = api_url[:-1]
    if action.startswith('/'):
        action = action[1:] 
    url_action = api_url + '/' + action

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f'sso-key {API_KEY}:{SECRET_KEY}'
    }

    if dryrun:
        print(' * dry_run * ', op, url_action, data)
        return None

    else:
        if verbose:
            print(url_action, data)

        response = requests.request(
            op,
            url_action,
            headers=headers,
            data=data
        )

        if verbose:
            print(response.status_code, response.text)

        return (response.status_code, response.text)

#
#
#
def get_dns_records(domain_name, dns_types=None):
    """ Return a list the dns types for a domain name """
    # print('Checking... ' + domain_name, dns_types)

    status, output = call_api('GET', f'v1/domains/{domain_name}/records')
    if status not in (STATUS_OK, STATUS_NOT_FOUND, STATUS_TOO_MANY_REQUESTS):
        print(f'ERROR: status {status}')
        exit(-1)

    dns_details = json.loads(output)

    res = []
    try:
        if 'code' in dns_details:
            error_code = dns_details['code']
            if error_code == 'TOO_MANY_REQUESTS':
                print(f'\r{error_code} Waiting 30s...     ', end = '\r')
                sleep(30)
                return get_dns_records(domain_name, dns_types)

            elif error_code == 'UNKNOWN_DOMAIN':
                # This domain has not that dns type
                return None
            else:
                print('UNKNOWN ERROR CODE', dns_details)
                exit(-1)
        else:
            if dns_types is None:
                res = dns_details
            else:
                # Filter the requested dns_types
                for record in dns_details:
                    if record['type'] in dns_types:
                        res.append(record)

    except:
        print('ERROR', dns_details)
        exit(-1)

    return res

#
#
#
def create_cloud_config_backup(dns_types, output_filename):
    res = {}

    status, output = call_api('GET', f'v1/domains')
    if (status != STATUS_OK):
        print(f'ERROR: status {status}')
        exit(-1)
    my_domains = json.loads(output)

    if 'code' in my_domains:
        print('ERROR:', my_domains)
        exit(-1)

    n_domains = len(my_domains)
    printProgressBar(0, n_domains)
    for i, domain in enumerate(my_domains):
        domain_name = domain['domain']
        printProgressBar(i + 1, n_domains, suffix = 'Complete - '+ domain_name)
        
        domain_dns = get_dns_records(domain_name, dns_types)
        if domain_dns is not None and len(domain_dns) > 0:
            res[domain_name] = domain_dns

    if output_filename is not None:
        with open(output_filename, 'w') as fp:
            json.dump(res, fp, indent=4)
        print(f'Created file {output_filename}')
    else:
        print(res)
    
    return res

#
#
#
def jd_update_to_dict(diff_map, state_cloud, state_desired):
    all_changes = {}
    # Changes in the domain's records
    for domain in diff_map:
        changes = all_changes.get(domain, {})
        for subaction in diff_map[domain]:
            if subaction == jd.insert:
                # New DNS record inserted
                for pos,data in diff_map[domain][subaction]:
                    record = state_desired[domain][pos]
                    changes[(record['type'], record['name'])] = []

            elif subaction == jd.delete:
                # DNS record deleted
                for pos in diff_map[domain][subaction]:
                    record = state_cloud[domain][pos]
                    changes[(record['type'], record['name'])] = []

            elif isinstance(subaction, int):
                # DNS record updated
                pos = subaction
                for subaction in diff_map[domain][pos]:
                    if subaction in (jd.insert, jd.update):
                        record = state_desired[domain][pos]
                        changes[(record['type'], record['name'])] = []
                    else:
                        print('ERROR: Subaction "'+ str(subaction) +'" TODO.')
                        exit(-1)

            else:
                print('ERROR: Subaction "'+ str(subaction) +'" not found')
                exit(-1)

        # Add all the records for the modified dns type/name
        for record in state_desired[domain]:
            if (record['type'], record['name']) in changes:
                changes[(record['type'], record['name'])].append(record)

        all_changes[domain] = changes

    return all_changes

#
#
#
def confirm_changes(all_changes):
    print('--- Changes to apply ----')
    print ("{:<35} {:<15} {:<50}".format('Domain_____','DNS Type/Name__','DNS Record_____'))
    for domain in all_changes:
        changes = all_changes[domain]
        for k in changes:
            dns_records = changes[k]
            for lns in dns_records:
                print ("{:<35} {:<15} {:<50}".format(domain, '/'.join(k), str(lns)))
            if dns_records == []:
                print ("{:<35} {:<15} {:<50}".format(domain, '/'.join(k), 'DELETE'))
    print('-'*100)

    confirmed = False
    answer = input("Continue [y/n]?")
    if answer.lower() in ["n","no"]:
        print('Cancelling update by user request')
    elif answer.lower() in ["y","yes"]:
        confirmed = True
    else:
        print('Invalid answer.')

    return confirmed
#
#
#
def update_cloud_config(dns_types, source_filename, is_dryrun):
    temp_filename = os.path.join(tempfile.mkdtemp(), str(time()))
    print('\n#1. Getting cloud state...')
    create_cloud_config_backup(dns_types, temp_filename)
    state_cloud = None
    with open(temp_filename, 'r') as f:
        state_cloud = json.load(f)
    os.remove(temp_filename)

    print(f'\n#2. Reading desired status file: {source_filename}')
    state_desired = None
    with open(source_filename, 'r') as f:
        state_desired = json.load(f)
    
    print('\n#3. Checking differences...')
    diffs = jd.diff(state_cloud, state_desired, syntax='explicit')
    if diffs == {}:
        print('No changes found between cloud and source code')
        exit(0)

    # Group changes by domain
    for action in diffs:
        if action == jd.insert:
            # New domain inserted (do we need to cover this??)
            for domain in diffs[action]:
                print('DOMAIN added:',domain)

        elif action == jd.delete:
            # Domain deleted (do we need to cover this??)  
            for domain in diffs[action]:
                print('DOMAIN deleted:',domain)

        elif action == jd.update:
            changes = jd_update_to_dict(diffs[action], state_cloud, state_desired)
            if not confirm_changes(changes):
                print('Update cancelled')
                exit(0)

            print('\n#4. Applying updates...')
            for domain in changes:
                for k in changes[domain]:
                    kType, kName = k
                    dns_records = changes[domain][k]
                    method_url = os.path.join('v1','domains',domain,'records', kType, kName)
                    if dns_records == []:
                        # Delete
                        status, output = call_api('DELETE', urllib.parse.quote(method_url), dryrun=is_dryrun)
                        if status != STATUS_OK_DELETE:
                            print('ERROR deleting', method_url, status, output)
                    else:
                        # Update
                        status, output = call_api('PUT', urllib.parse.quote(method_url), data=json.dumps(dns_records), dryrun=is_dryrun)
                        if status != STATUS_OK:
                            print('ERROR updating', method_url, status, output)

        else:
            # New domain inserted (do we need to cover this??)
            domain = action
            print('DOMAIN new:', domain)


#
# === MAIN ===
#
if __name__ == '__main__':
    action_list = ['backup', 'update']

    parser = argparse.ArgumentParser(description="Just an example", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-o", "--output", default=None, type=str, help="Filename where to write the results ")
    parser.add_argument("-s", "--source", default=None, type=str, help="Filename with the source code representing the desired status")
    parser.add_argument("-t", "--records_type", type=str, help="Comma separated type of DNS records to perform the action to")
    parser.add_argument("--dry", action="store_true", help="Print out the actions to apply but without actually applying them")
    parser.add_argument("action", help="[ " + ' | '.join(action_list) + " ]")
    parser.add_argument("scope", help="Suffix for the env variable to use as api key. Variables: GODADDY_API_KEY_<scope> / GODADDY_API_KEY_<scope>")

    if len(sys.argv) < 2:
        parser.print_help()
        exit(-1)

    args = parser.parse_args()
    config = vars(args)

    # Config
    action = config['action']
    scope = config['scope']
    records_type = config['records_type']
    output_filename = config['output']
    source_filename = config['source']
    is_dryrun = config['dry']

    if not action in action_list:
        print('Invalid value for "action". It should be ', action_list)
        exit(-1)

    load_dotenv() # Take environment variables from .env


    dns_types = records_type.split(',') if records_type is not None else None

    # -- Actions
    if action == 'backup':
        create_cloud_config_backup(dns_types, output_filename)

    elif action == 'update':
        if source_filename is None:
            print('Action needs the --source paramenter to be populated')
            exit(-1)
        update_cloud_config(dns_types, source_filename, is_dryrun)

    print('Done.')

