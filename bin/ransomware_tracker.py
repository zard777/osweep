#!/opt/splunk/bin/python
"""
Description: Use Ransomware Tracker to distinguish threats between ransomware 
botnet Command & Control servers (C&Cs), ransomware payment sites, and ransomware 
distribution sites. The script accepts a list of strings (domain, IP, malware
family, site status, threat type, and/or URL):
    | ransomwareTracker <IOCs>

or input from the pipeline (any field where the value is a domain, IP, malware
family, site status, threat type, and/or URL). The first argument is the name of 
one field:
    <search>
    | fields <FIELD>
    | ransomwareTracker <FIELD>

Source: https://ransomwaretracker.abuse.ch/tracker/

Instructions:
1. Manually download URL dump (one-time)  
```
| ransomwareTracker feed
```
2. Switch to the Ransomware Tracker dashboard in the OSweep app.
3. Add the list of IOCs to the "Domain, IP, Malware, Status, Threat, URL (+)" 
textbox.
4. Select whether the results will be grouped and how from the dropdowns.
5. Click "Submit".

Rate Limit: None

Results Limit: None

Notes: None

Debugger: open("/tmp/splunk_script.txt", "a").write("{}: <MSG>\n".format(<VAR>))
"""

from collections import OrderedDict
import os
import re
import sys

script_path = os.path.dirname(os.path.realpath(__file__)) + "/_tp_modules"
sys.path.insert(0, script_path)
from HTMLParser import HTMLParser
import validators

import commons


def get_feed():
    """Return the latest report summaries from the feed."""
    api     = "https://ransomwaretracker.abuse.ch/feeds/csv/"
    session = commons.create_session()
    resp    = session.get(api)

    if resp.status_code == 200 and resp.text != "":
        data    = resp.text.splitlines()
        data    = data[8:-1]
        data[0] = data[0][2:]
        header  = data[0].split(",")
        data_feed = []

        for line in data[1:]:
            line = line.replace('","', "^^")
            line = line.replace(",", " ")
            line = line.replace("^^", ",")
            line = line.replace('"', " ")
            ransomware_data = line.split(",")
            ransomware_dict = OrderedDict(zip(header, ransomware_data))
            data_feed.append(ransomware_dict)
        return data_feed
    return

def write_file(data_feed, file_path):
    """Write data to a file."""
    if data_feed == None:
        return

    with open(file_path, "w") as open_file:
        keys   = data_feed[0].keys()
        header = ",".join(keys)

        open_file.write("{}\n".format(header))

        for data in data_feed:
            data_string = ",".join(data.values())
            open_file.write("{}\n".format(data_string.encode("UTF-8")))
    return

def process_iocs(results):
    """Return data formatted for Splunk from Ransomware Tracker."""
    if results != None:
        provided_iocs = [y for x in results for y in x.values()]
    else:
        provided_iocs = sys.argv[1:]

    splunk_table = []
    lookup_path  = "/opt/splunk/etc/apps/osweep/lookups"
    open_file    = open("{}/ransomware_tracker_feed.csv".format(lookup_path), "r")
    data_feed    = open_file.read().splitlines()
    header       = data_feed[0].lower().split(",")
    open_file.close()

    open_file = open("{}/ransomware_tracker_malware.csv".format(lookup_path), "r")
    malware   = set(open_file.read().splitlines()[1:])
    malware   = [x.lower() for x in malware]
    open_file.close()

    open_file = open("{}/ransomware_tracker_threats.csv".format(lookup_path), "r")
    threats   = set(open_file.read().splitlines()[1:])
    threats   = [x.lower() for x in threats]
    open_file.close()

    for provided_ioc in set(provided_iocs):
        provided_ioc = provided_ioc.replace("htxp", "http")
        provided_ioc = provided_ioc.replace("hxtp", "http")
        provided_ioc = provided_ioc.replace("hxxp", "http")
        provided_ioc = provided_ioc.replace("[.]", ".")
        provided_ioc = provided_ioc.replace("[d]", ".")
        provided_ioc = provided_ioc.replace("[D]", ".")

        if not validators.domain(provided_ioc) and \
           not validators.ipv4(provided_ioc) and \
           not validators.url(provided_ioc) and \
           provided_ioc.lower() not in malware and \
           provided_ioc.lower() not in threats:
           splunk_table.append({"invalid": provided_ioc})
           continue

        line_found = False
        for line in data_feed:
            if provided_ioc.lower() in line.lower():
                line_found      = True
                ransomware_data = line.split(",")
                ransomware_dict = OrderedDict(zip(header, ransomware_data))
                splunk_table.append(ransomware_dict)

        if line_found == False:
            splunk_table.append({"no data": provided_ioc})
    return splunk_table

if __name__ == "__main__":
    if sys.argv[1].lower() == "feed":
        data_feed    = get_feed()
        lookup_path  = "/opt/splunk/etc/apps/osweep/lookups"
        file_path    = "{}/ransomware_tracker_feed.csv".format(lookup_path)
        malware_list = "{}/ransomware_tracker_malware.csv".format(lookup_path)
        threat_list  = "{}/ransomware_tracker_threats.csv".format(lookup_path)

        with open(malware_list, "w") as mfile, open(threat_list, "w") as tfile:
            mfile.write("malware\n")
            tfile.write("threat\n")

            malwares = []
            threats  = []
            for data in data_feed:
                malware = data["Malware"].encode("UTF-8")
                threat  = data["Threat"].encode("UTF-8")

                if malware not in malwares:
                    mfile.write("{}\n".format(malware))

                if threat not in threats:
                    tfile.write("{}\n".format(threat))

        write_file(data_feed, file_path)
        exit(0)

    current_module = sys.modules[__name__]
    commons.return_results(current_module)
