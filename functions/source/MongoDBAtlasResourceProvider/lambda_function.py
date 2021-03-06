""" This is the MongoDB Atlas Resource Provider for AWS CloudFormation
Quickstart - lambda handler
"""
# pylint: disable=W1203

# pylint: disable=C0103
import logging
from time import sleep
import traceback
import os

import requests
from requests.auth import HTTPDigestAuth
import cfnresponse


log = logging.getLogger()
log.setLevel(logging.DEBUG)

def make_PRI(kind_id_pair_list=[]):
    """ Make correct forrmatted PhysicalResourceId
    append to pri if you pass it in.
    For example,
    [ ("project","123"), ("cluster","456"), ... ]
    returns:
    "project:123,cluster:456,..."
    """
    pri = ','.join(f"{kind}:{id}" for (kind,id) in kind_id_pair_list)
    log.debug(f"make_PRI: kind_id_pair_list={kind_id_pair_list}, pri={pri}")
    return pri

def parse_id_from_physical_resource_id(pri, kind=None):
    """ We store PRI AWS CFN 'PhysicalResourceId' formatted with the
    MongoDB Atlas "id" and also the type of resource, for example:
    project:12354, project:212332,cluster:94872736, project:12345,peer:9439373723
    When need, like for cluster the parent id is first. So you can always
    fetch the "id" of "this" resource by splitting on comma and grab the last piece.
    """
    if kind == None:
        this_id_info = pri.split(',')[-1]
    else:
        this_id_info = ""
        parts = pri.split(",")
        for part in parts:
            (k, i) = part.split(":")
            if k == kind:
                this_id_info = part
    log.debug(f"parse_id_from_physical_resource_id pri={pri}, kind={kind}, this_id_info={this_id_info}")
    if ":" not in this_id_info:
        log.warn("Invalid id format - no ':' in id!")
        return this_id_info
    (this_kind, this_id) = this_id_info.split(":")
    if this_kind == kind:
        return this_id
    else:
        log.error(f"wrong kind! this_kind:{this_kind}")
        return None

def _p(e):
    """ Internal: pull a projectId from a Pysical Resource ID
    """
    return parse_id_from_physical_resource_id(e[PRI], "project")

def _api(evt, ep, m="GET", d={}, eatable=False):
    """ Internal wraps api access from event
    """
    pub = evt[RP].get("PublicKey", "")
    pvt = evt[RP].get("PrivateKey", "")
    log.debug(f"**REMOVE** pub:{pub}")
    log.debug(f"**REMOVE** pvt:{pvt}")

    return __api(pub, pvt, ep, m, d, eatable)


def __api(pub, pvt, ep, m="GET", d={}, eatable=False):
    """ Internal - wraps all api access
    """
    if m == "GET":
        r = requests.get(ep, auth=HTTPDigestAuth(pub, pvt), params=d)
    elif m == "DELETE":
        r = requests.delete(ep, auth=HTTPDigestAuth(pub, pvt))
    elif m == "POST":
        r = requests.post(
            ep,
            auth=HTTPDigestAuth(pub, pvt),
            headers={"Content-Type": "application/json"},
            json=d,
        )
    else:
        raise Exception(f"bad m:{m}")

    j = r.json()
    log.info(f"_api m:{m} json:{j}")
    if "error" in j:
        if eatable and (j["errorCode"] in OK_DELETE_ERRORCODES):
            log.warning(f"OK ERROR DETECTED: Error: {j}")
            return {
                "Code": "STOP",
                "Message": "Ok error response from MongoDB Cloud detected.",
            }
        else:
            log.warning(traceback.print_exc())
            raise Exception(j)
    return j


# check if we deployed with environment variable Atlas API KEY
def try_load_deploy_key():
    """ Test out the key we were deployed with
    and see if it's good
    """
    DEPLOY_KEY = {
        "PUBLIC_KEY": os.getenv("PUBLIC_KEY", "NOT-FOUND"),
        "PRIVATE_KEY": os.getenv("PRIVATE_KEY", "NOT-FOUND"),
        "ORG_ID": os.getenv("ORG_ID", "NOT-FOUND"),
    }
    print(f"try_load_deploy_key, DEPLOY_KEY:{DEPLOY_KEY}")

    try:
        org_resp = __api(DEPLOY_KEY["PUBLIC_KEY"],
                         DEPLOY_KEY["PRIVATE_KEY"],
                         f"https://cloud.mongodb.com/api/atlas/v1.0/orgs/{DEPLOY_KEY['ORG_ID']}")
        print(f"org_resp={org_resp}")
        VALID_DEPLOY_KEY = (org_resp != None)
        print(f"Tried to validate DEPLOY_KEY:{DEPLOY_KEY}, VALID_DEPLOY_KEY:{VALID_DEPLOY_KEY}")
    except Exception as e:
        log.error(e)
        log.warning(f"ERROR: {e}")
        VALID_DEPLOY_KEY = False
    return (VALID_DEPLOY_KEY, DEPLOY_KEY)

#VALID_DEPLOY_KEY, DEPLOY_KEY = try_load_deploy_key()
#log.info(f"##REMOVE##~~~> DEPLOY_KEY:{DEPLOY_KEY}")
#log.info(f"##REMOVE##~~~> VALID_DEPLOY_KEY:{VALID_DEPLOY_KEY}")
RESP_DATA = "Data"
RP = "ResourceProperties"
RT = "RequestType"
PRI = "PhysicalResourceId"
MDBg = "https://cloud.mongodb.com/api/atlas/v1.0/groups"
PRID = "X"
CS = "connectionStrings"
OK_DELETE_ERRORCODES = [
    "GROUP_NOT_FOUND",
    "NOT_IN_GROUP",
    "CLUSTER_ALREADY_REQUESTED_DELETION",
    "INVALID_GROUP_ID",
]


CREATING_PRI = ""


def validate_resource_type(rt, target_type):
    """ Returns True if the rt is a valid target_type
    For example, both Custom::AtlasDeployment
    and MongoDB::Atlas::Deployment are valid ATLAS_DEPLOYMENT_RESOURCE_TYPE's
    """
    parts = rt.split("::")
    log.info(f"validate_resource_type rt:{rt}, parts:{parts}, target_type:{target_type}")
    if not len(parts) > 0:
        return False
    if parts[0] == "Custom":
        if not 'Atlas' in parts[1]:
            return False
        this_type = parts[1].split("Atlas")[1]
        log.info(f"Custom: this_type:{this_type}")
        if this_type == target_type:
            return True
    elif parts[0] == "MongoDB":
        if not parts[1]=="Atlas":
            return False
        this_type = parts[2]
        log.info(f"MongoDB::Atlas:: - strong type: this_type:{this_type}")
        if this_type == target_type:
            return True
    return False


def create(evt):
    """ Create a new Atlas deployment
    """
    log.info(f"create:evt:{evt}")
    resource_type = evt["ResourceType"]
    log.info(f"create:resource_type:{resource_type}")
    if validate_resource_type(resource_type,"Deployment"):
        return handle_deployment_create(evt)
    elif validate_resource_type(resource_type,"Cluster"):
        return handle_cluster_create(evt)
    elif validate_resource_type(resource_type,"Peer"):
        return handle_peer_create(evt)

    # what to do else?

def handle_deployment_create(evt):
    p = evt[RP]
    prj = p["Project"]
    if "OrgId" in evt[RP]:
        # This allows add OrgId from DEPLOY_KEY injected into evt
        org_id = evt[RP]["OrgId"]
        log.info(f"Found org_id:{org_id} in event, setting project orgId")
        prj["orgId"] = org_id

    log.info(f"create- try create prj:{prj}")
    pR = _api(evt, f"{MDBg}", m="POST", d=prj)
    resp = {}
    pid = pR["id"]
    prid = make_PRI([("project",pid)])
    resp[PRI] = prid
    CREATING_PRI = prid
    # Database Users
    _d = []
    for dbu in p.get("DatabaseUsers"):
        dbu["groupId"] = pid
        dbr = _api(evt, f"{MDBg}/{pid}/databaseUsers", m="POST", d=dbu)
        _d.append(dbr)
    # Cloud Provider Access
    ecpa = _api(
        evt, f"{MDBg}/{pid}/cloudProviderAccess", m="POST", d={"providerName": "AWS"}
    )
    for k in ecpa:
        resp[f"cloudProviderAccess-{k}"] = ecpa[k]
    # Access List (ip - peering and privatelink are separate resources)
    if "AccessList" in p:
        access_list_req = p["AccessList"]
        entry_type = access_list_req["accessListType"]
        if entry_type == "NONE":
            log.warn(f"Found NONE AccessListType, skipping.... access_list_req:{access_list_req}")
        else:
            entry_value = access_list_req["accessListValue"]
            ac = { entry_type : entry_value,
                   "comment" : access_list_req["Comment"] }
            log.info(f"access list attempt create ac:{ac}")
            resp["accessList"] = _api(evt, f"{MDBg}/{pid}/accessList", m="POST", d=ac)
    resp["project"] = _api(evt, f"{MDBg}/{pid}")
    return {RESP_DATA: resp, PRI: prid}


def handle_cluster_create(evt):

    p = evt[RP]

    # Lookup project reference
    prj = p["Project"]

    log.info(f"handle_cluster input from template prj:{prj}")
    try_id = prj.get("id","NOT-FOUND")

    pid = parse_id_from_physical_resource_id(try_id,"project")
    log.info(f"lookedup AWS org:project to get pid:{pid}")
    if pid == "NOT-FOUND":
        raise Exception("Did not find project id in input parameters")


    prj["id"]=pid
    pR = _api(evt, f"{MDBg}/{pid}")
    resp = {}
    pid = pR["id"]


    # Note - seeding the pysical resource id with cluster "tbd"
    prid = make_PRI([ ("project",pid), ("cluster", "TBD") ])
    resp[PRI] = prid
    CREATING_PRI = prid
    # Finally, cluster since it takes time
    if "Cluster" in p:
        c = p["Cluster"]
        # Set to AWS, obviously
        c.get("providerSettings", {})["providerName"] = "AWS"
        aws_region = c["providerSettings"]["regionName"]
        mdb_region = aws_region.upper().replace("-", "_")
        log.info(f"Translated aws_region:{aws_region} to mdb_region:{mdb_region}")
        c["providerSettings"]["regionName"] = mdb_region
        log.info(f"Attempt to create new cluster:{c}")
        ce = f"{MDBg}/{pid}/clusters"
        cr = _api(evt, ce, m="POST", d=c)
        log.info(f"Create cluster response cr:{cr}")
        # Note - fix up the PRI physical resource id since cluster created
        prid = make_PRI( [ ("project",pid), ("cluster",cr['id']) ] )
        resp["SrvHost"] = wait_for_cluster(evt, ce, 5)
    resp["project"] = _api(evt, f"{MDBg}/{pid}")
    return {RESP_DATA: resp, PRI: prid}



def wait_for_cluster(evt, ep, m=1):
    """ Wait some mins until the cluster is IDLE
    """
    log.info(f"{m}min wait cluster")
    sleep(m * 60)
    c = _api(evt, ep)["results"][0]
    if c.get("stateName") == "IDLE":
        return c.get("srvAddress")
    return wait_for_cluster(evt, ep, 1)

def wait_for_cluster_delete(evt, pid, m=1):
    """ Wait some mins until the cluster is DELETEd
       ep should be to groups/{pid} because this will
       return done when the project clusterCount == 0
    """
    log.info(f"{m}min wait_for_cluster_delete -- (condition checked: project.clusterCount==0) ")
    sleep(m * 60)
    p = _api(evt, f"{MDBg}/{pid}")
    lgo.info(f"wait_for_cluster_delete p:{p}")
    if p.get("clusterCount", "NOT-FOUND") == 0:
        return p
    return wait_for_cluster(evt, pid, 1)


def handle_peers_update(evt):
    log.info("handle_peers_update ---")
    return handle_peer_create(evt)

def handle_peer_create(evt):


    p = evt[RP]

    # Lookup project reference
    prj = p["Project"]

    log.info(f"handle_cluster input from template prj:{prj}")
    try_id = prj.get("id","NOT-FOUND")
    pid = parse_id_from_physical_resource_id(try_id,"project")
    log.info(f"lookedup AWS org:project to get pid:{pid}")
    if pid == "NOT-FOUND":
        raise Exception("Did not find project id in input parameters")
    prj["id"]=pid
    pR = _api(evt, f"{MDBg}/{pid}")
    resp = {}
    pid = pR["id"]

    if "Peer" not in p:
        log.info(f"Peer was NOT in p: {p}")
        raise Exception("Did not find 'Peer'")


    # Note - seeding the pysical resource id with peer "tbd"
    prid = make_PRI([ ("project",pid), ("peer", "TBD") ])
    resp[PRI] = prid
    CREATING_PRI = prid

    peer_req = p['Peer']
    # seems first we need see if there is already an AWS
    # "container" whatever this is?
    existing_containers = _api(evt, f"{MDBg}/{pid}/containers",d={"providerName": "AWS"})
    log.debug(f"existing_containers:{existing_containers}")
    if existing_containers['totalCount'] >= 1:  # we have one
        container = existing_containers['results'][0]
        log.info(f"loaded existing container:{container}")
    else:
        log.info("No existing containers, try create one")
        atlasCidrBlock = peer_req.get("routeTableCidrBlock","10.0.0.0/16")
        regionName = peer_req.get("regionName").upper().replace("-", "_")
        container_req = { "atlasCidrBlock" : atlasCidrBlock,
                          "providerName" : "AWS",
                          "regionName" : regionName }
        log.info(f"try create container container_req:{container_req}")
        container = _api(evt, f"{MDBg}/{pid}/containers",m="POST",d=container_req)
        log.info(f"created container: container:{container}")
    log.warn(f"Need to use this atlasCidrBlock to complete the peering request in the route table.")
    peering_req = {
        "accepterRegionName" : peer_req["accepterRegionName"],
        "awsAccountId" : peer_req["awsAccountId"],
        "containerId" : container["id"],
        "providerName" : "AWS",
        "routeTableCidrBlock" : peer_req["routeTableCidrBlock"],
        "vpcId" : peer_req["vcpId"],
    }
    log.info(f"try create peering peering_req:{peering_req}")
    peering_resp = _api(evt, f"{MDBg}/{pid}/peers",m="POST",d=peering_req)
    log.info(f"created peering: peering_resp:{peering_resp}")
    prid = make_PRI([ ("project",pid), ("peer", peering_resp['id']) ])
    resp[PRI] = prid
    log.info(f"prid:{prid}")
    return {resp_data: resp, pri: prid}



def update(evt):
    """ Handle the update event
    This needs work
    """
    log.info(f"update:evt:{evt}")
    prj = _api(evt, f"{MDBg}/{_p(evt)}")
    r = {PRI: evt[PRI]}
    r[RESP_DATA] = {}
    pid = prj["id"]
    resource_type = evt["ResourceType"]
    log.info(f"create:resource_type:{resource_type}")

    if validate_resource_type(resource_type,"Peer"):
      return handle_peers_update(evt)

    if int(prj["clusterCount"]) > 0:
        c = _api(evt, f"{MDBg}/{pid}/clusters/{evt[RP]['Name']}")
        r[RESP_DATA]["SrvHost"] = c.get("srvAddress", c.get("stateName"))
    e = _api(evt, f"{MDBg}/{pid}/cloudProviderAccess")
    for k in e["awsIamRoles"][0]:
        r[RESP_DATA][f"cloudProviderAccess-{k}"] = e["awsIamRoles"][0][k]
    if "accessList" in prj["AccessList"]:
        r[RESP_DATA]["accessList"] = _api(
            evt, f"{MDBg}/{pid}/accessList", m="POST", d=prj["AccessList"]
        )
    return r

def delete(evt):
    """ Delete a new Atlas deployment
    """
    log.info(f"delete:evt:{evt}")
    resource_type = evt["ResourceType"]
    log.info(f"delete:resource_type:{resource_type}")
    if validate_resource_type(resource_type,"Deployment"):
        return handle_deployment_delete(evt)
    elif validate_resource_type(resource_type,"Cluster"):
        return handle_cluster_delete(evt)
    elif validate_resource_type(resource_type,"Peer"):
        return handle_peer_delete(evt)

    # what to do else?

def handle_deployment_delete(evt):
    """ Deal with deletes.
    This works well, it will first try delete the cluster and wait
    to clean up the project. It tries to lookup byName and also returns
    SUCCESS when a "bad" ID comes in, probably broker deployment and nothing
    on the MongoDB-side to clean up, so clean up the cfn side of house.
    """
    name = evt[RP]["Name"]

    try_id = evt[PRI]
    if "LATEST" in try_id:
        log.info(f"Broken deployment invalid id format: {try_id}. Cleaning up")
        # Note - we just return without error here, this will
        # "clean up" the cfn resource on the AWS-side
        # we don't have anything to clean up on the MongoDB side
        return {
            RESP_DATA: {"Message": "Cleaning up invalid id resource"},
            PRI: evt[PRI],
        }

    pid = parse_id_from_physical_resource_id(try_id,"project")
    log.info(f"lookedup AWS org:project to get pid:{pid}")
    try:
        r = _api(evt, f"{MDBg}/{pid}", m="DELETE", eatable=True)
        log.info(f"DELETE project r:{r}")
        return {RESP_DATA: r, PRI: evt[PRI]}
    except Exception as e:
        log.warning(f"ERROR: {e}")
        return {RESP_DATA: {"Error": str(e), PRI: evt[PRI]}}

def handle_cluster_delete(evt):
    """ Deal with cluster deletes.
    This works well, it will first try delete the cluster and wait
    to clean up the project. It tries to lookup byName and also returns
    SUCCESS when a "bad" ID comes in, probably broker deployment and nothing
    on the MongoDB-side to clean up, so clean up the cfn side of house.
    """

    try_id = evt[PRI]
    if "LATEST" in try_id:
        log.info(f"Broken deployment invalid id format: {try_id}. Cleaning up")
        # Note - we just return without error here, this will
        # "clean up" the cfn resource on the AWS-side
        # we don't have anything to clean up on the MongoDB side
        return {
            RESP_DATA: {"Message": "Cleaning up invalid id resource"},
            PRI: evt[PRI],
        }

    pid = parse_id_from_physical_resource_id(try_id,"project")
    log.info(f"lookedup AWS org:project to get pid:{pid}")


    prj = _api(evt, f"{MDBg}/{pid}", eatable=True)
    log.info(f"delete prj:{prj}")
    pid = prj["id"]
    if int(prj["clusterCount"]) > 0:
        name = evt[RP]["Name"]
        cd = _api(evt, f"{MDBg}/{pid}/clusters/{name}", m="DELETE", eatable=True)
        log.info(f"cluster delete response cd:{cd}")
        return {RESP_DATA: cd, PRI: evt[PRI]}
    else:
        log.info(f"DELETE Cluster but clusterCount={prj['clusterCount']} was not > 0")
        return {RESP_DATA: {}, PRI: evt[PRI]}


def handle_peer_delete(evt):
    """ Deal with Peer deletes.
    """
    try_id = evt[PRI]
    if "LATEST" in try_id:
        log.info(f"Broken deployment invalid id format: {try_id}. Cleaning up")
        # Note - we just return without error here, this will
        # "clean up" the cfn resource on the AWS-side
        # we don't have anything to clean up on the MongoDB side
        return {
            RESP_DATA: {"Message": "Cleaning up invalid id resource"},
            PRI: evt[PRI],
        }

    pid = parse_id_from_physical_resource_id(try_id,"project")
    log.info(f"lookedup AWS org:project to get pid:{pid}")

    peer_id = parse_id_from_physical_resource_id(try_id,"peer")
    log.info(f"delete peer - peer_id:{peer_id}")

    cd = _api(evt, f"{MDBg}/{pid}/peers/{peer_id}", m="DELETE", eatable=True)
    log.info(f"peer delete response cd:{cd}")
    return {RESP_DATA: cd, PRI: evt[PRI]}


fns = {"Create": create, "Update": update, "Delete": delete}

def lambda_handler(evt, ctx):
    """ Main handler
    """
    log.info(f"got evt {evt}")
    rd = {}
    try:
        # lookup name of right function and call it, create/update/delete
        VALID_DEPLOY_KEY, DEPLOY_KEY = try_load_deploy_key()
        log.info(f"lambda_handler - try-load--> DEPLOY_KEY:{DEPLOY_KEY}, VALID_DEPLOY_KEY:{VALID_DEPLOY_KEY}")
        if VALID_DEPLOY_KEY:
            log.debug("Injecting deployed apikey into event payload")
            evt[RP]["PublicKey"] = DEPLOY_KEY["PUBLIC_KEY"]
            evt[RP]["PrivateKey"] = DEPLOY_KEY["PRIVATE_KEY"]
            evt[RP]["OrgId"] = DEPLOY_KEY["ORG_ID"]
        # now call the right handler function
        rd = fns[evt[RT]](evt)
        log.info(f"rd:{rd}")
        if PRI not in rd:
            log.error(f"No PRI:{PRI} in rd:{rd}")
            raise Exception(rd)
        cfnresponse.send(evt, ctx, cfnresponse.SUCCESS, rd[RESP_DATA], rd[PRI])
    except Exception as error:
        log.error(error)
        cfnresponse.send(
            evt, ctx, cfnresponse.FAILED, {"error": str(error)}, CREATING_PRI
        )


def test_entrypoint(evt, ctx):
    """ Not really used yet, needs testing!
    """
    log.info(f"test_entrypoint! does it work? {evt} {ctx}")
    cfnresponse.send(
        evt, ctx, cfnresponse.FAILED, {"error": "Not implemented, yet"}, None
    )
