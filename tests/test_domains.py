""" Test domains.py """

# pylint: disable=import-error

import pytest
import os
import json
from dotenv import load_dotenv
import domains

test_dotenv_filename = 'env_sample'

RESPONSE_GET_DOMAINS = '''
[
    {
        "createdAt": "2021-12-26T22:27:47.000Z", 
        "domain": "demo_domain.com", 
        "domainId": 2104040, 
        "expirationProtected": false, 
        "expires": "2024-12-26T22:27:47.000Z", 
        "exposeWhois": false, 
        "holdRegistrar": false, 
        "locked": true, 
        "nameServers": null, 
        "privacy": false, 
        "registrarCreatedAt": "2021-12-26T15:27:44.547Z", 
        "renewAuto": true, 
        "renewDeadline": "2025-02-09T22:27:47.000Z", 
        "renewable": true, 
        "status": "ACTIVE", 
        "transferProtected": false
    }
]
'''

RESPONSE_GET_DNS_RECORDS = '''
[
    { "data": "Parked", "name": "@", "ttl": 600, "type": "A" },
    { "data": "ns01.ote.domaincontrol.com", "name": "@", "ttl": 3600, "type":"NS" },
    { "data": "ns02.ote.domaincontrol.com", "name": "@", "ttl": 3600, "type":"NS" },
    { "data": "@", "name": "www", "ttl": 3600, "type": "CNAME" },
    { "data": "_domainconnect.ss.domaincontrol.com", "name": "_domainconnect", "ttl": 3600, "type": "CNAME" }
]
'''

def test_call_api_mandatory_api_key():
    action = 'GET'
    action_call = 'v1/domains'

    if 'GODADDY_API_KEY' in os.environ:
        del os.environ['GODADDY_API_KEY']

    if 'GODADDY_SECRET_KEY' in os.environ:
        del os.environ['GODADDY_SECRET_KEY']

    with pytest.raises(SystemExit) as excinfo:
        domains.call_api(action, action_call)

    assert excinfo.value.code == -1

def test_call_api_mandatory_secret_key():
    action = 'GET'
    action_call = 'v1/domains'

    load_dotenv(test_dotenv_filename) 
    del os.environ['GODADDY_SECRET_KEY']

    with pytest.raises(SystemExit) as excinfo:
        domains.call_api(action, action_call)

    assert excinfo.value.code == -1

def test_call_api_demo_connection():
    action = 'GET'
    action_call = 'v1/domains'

    load_dotenv(test_dotenv_filename) 

    status, output = domains.call_api(action, action_call)

    assert status == 200

    data = json.loads(output)
    assert data != []
    assert 'domain' in data[0].keys()
    assert 'nameServers' in data[0].keys()
    assert 'status' in data[0].keys()

    return data[5]

def test_get_dns_records_all(mocker):

    domain_name = 'demo_domain'
    mocker.patch('domains.call_api', return_value=(200, RESPONSE_GET_DNS_RECORDS) ) 
    
    res = domains.get_dns_records(domain_name, verbose=True)
    
    print(res)
    assert len(res) == 5

def test_get_dns_records_filtered(mocker):

    domain_name = 'demo_domain'
    mocker.patch('domains.call_api', return_value=(200, RESPONSE_GET_DNS_RECORDS) ) 
    
    res = domains.get_dns_records(domain_name, dns_types=['NS'], verbose=True)
    
    print(res)
    assert len(res) == 2

def test_get_dns_records_with_error_domain(mocker):

    domain_name = 'demo_domain'
    mocker.patch('domains.call_api', return_value=(200, ''' { "code": "UNKNOWN_DOMAIN"} ''') ) 
    
    res = domains.get_dns_records(domain_name, verbose=True)
    print(domain_name)
    assert res == None

def test_get_dns_records_with_error_other(mocker):

    domain_name = 'demo_domain'
    mocker.patch('domains.call_api', return_value=(200, ''' { "code": "UNKNOWN_ERROR"} ''') ) 

    with pytest.raises(SystemExit) as excinfo:
        domains.get_dns_records(domain_name, verbose=True)

    assert excinfo.value.code == -1

def test_create_cloud_config_backup_with_status_error(mocker):
    mocker.patch('domains.call_api', return_value=(200, json.loads(RESPONSE_GET_DOMAINS)) ) 
    mocker.patch('domains.get_dns_records', return_value=(200, json.loads(RESPONSE_GET_DNS_RECORDS)) ) 

    # dns_types = []
    # output_filename = 'output_test_status_error.json'
    # domains.create_cloud_config_backup(dns_types, output_filename)

def test_create_cloud_config_backup_with_code_error(mocker):
    pass

def test_create_cloud_config_backup_with_dns_records(mocker):
    pass

def test_create_cloud_config_backup_with_no_dns_records(mocker):
    pass

