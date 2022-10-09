# GoDaddy scripts 

## Usage

### Prepare environment
> python -m venv venv  
> source venv/bin/activate  
> pip install -r requirements.txt  

### Help
> python domains.py --help
```
usage: domains.py [-h] [-e ENVIRONMENTS] [-o OUTPUT] [-s STATE] [-t RECORDS_TYPE] [--dry] [--no_verify] [--verbose] action

GoDaddy Management Tool

positional arguments:
  action                [ import | plan | apply | audit_r53 ]

optional arguments:
  -h, --help            show this help message and exit
  -e ENVIRONMENTS, --environments ENVIRONMENTS
                        Filename where to write the results (default: .env)
  -o OUTPUT, --output OUTPUT
                        Filename where to write the results (default: None)
  -s STATE, --state STATE
                        Filename with the state information representing the desired status (plan/apply) (default: None)
  -t RECORDS_TYPE, --records_type RECORDS_TYPE
                        Comma separated type of DNS records to perform the action to (default: None)
  --dry                 Print out the actions to apply but without actually applying them (default: False)
  --no_verify           Disable security certificate checks. You may need this if using the Rapid7 agent (default: True)
  --verbose             Shows the requests calls information (default: False)
```

### import 
It creates a json file with the dns_records imported from all the GoDaddy domains. It will filter the dns_types if the *--records_type* parameter is provided.  
The default output filename is "godaddy_state.json"
> python domains.py import -e mykeys.env -o my_current_status.json

### plan
It creates a json file with the dns_records to modify if we want to achieve the "my_desired_state" state.  
The default state filename is "godaddy_state.json"  
The default output filename is "godaddy_plan.json"
> domains.py plan -e mykeys.env -s my_desired_state.json -o myplan.json 

### apply 
Apply the changes recorded in the plan file.  
The default plan filename is "godaddy_plan.json"
> python domains.py apply -e mykeys.env -s myplan.json

### audit_r53 
It checks all the domains not using Route53 name servers and having MX or TXT dns_records. It will save the result in a json file.  
The default output filename is "godaddy_audit_r53.json"

> python domains.py audit_r53 -e mykeys.env 

## Test
For running the test suite:
> python -m pytest tests


