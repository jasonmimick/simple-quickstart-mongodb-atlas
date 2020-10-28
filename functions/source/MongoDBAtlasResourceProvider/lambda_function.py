# pylint: disable=W1203
# pylint: disable=C0103
import logging
from time import sleep
import traceback
import os
import re

import requests
from requests.auth import HTTPDigestAuth
import boto3
from botocore.exceptions import ClientError
import cfnresponse


log = logging.getLogger()
#log.setLevel(logging.DEBUG)

# check if we deployed with environment variable Atlas API KEY
DEPLOY_KEY = {
    "PUBLIC_KEY": os.getenv("PUBLIC_KEY", "NOT-FOUND"),
    "PRIVATE_KEY": os.getenv("PRIVATE_KEY", "NOT-FOUND"),
    "ORG_ID": os.getenv("ORG_ID", "NOT-FOUND"),
}
print(f"Initial startup, DEPLOY_KEY:{DEPLOY_KEY}")
try {
    org_resp = __api(DEPLOY_KEY["PUBLIC_KEY"],
                     DEPLOY_KEY["PRIVATE_KEY"],
                     f"https://cloud.mongodb.com/api/atlas/v1.0/orgs/{DEPLOY_KEY['ORG_ID]}")
    log.debug(f"org_resp={org_resp}")
    VALID_DEPLOY_KEY = (org_resp != None)
    log.warning(f"Tried to validate DEPLOY_KEY: VALID_DEPLOY_KEY:{VALID_DEPLOY_KEY}")
except Exception as e:
    log.error(e)
    log.warning(f"ERROR: {e}")
    VALID_DEPLOY_KEY = False
log.info(f"##REMOVE##~~~> DEPLOY_KEY:{DEPLOY_KEY}")
DS = 30  # Sleep 30 seconds after cluster delete before deleting project
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


def resolve_secretmanager_ref(ref):
    """
    {{resolve:secretsmanager:SomeSecretNameFoo:SecretString:PublicKey}}
    """
    if type(ref) is str and re.match(r"{{resolve:secretsmanager:.*}}", ref):
        key_name = ref.split("{{")[1].split("}}")[0].split(":")[-1]
        secret_name = ref.split("{{")[1].split("}}")[0].split(":")[-3]
        return (secret_name, key_name)
    else:
        return (None, None)


def read_secret(secret_name):
    """ Internal util to read
    an AWS Secret
    """
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager")

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        # Some error happened here. Log it / handle it / raise it.
        log.error(f"Error read_secret e:{e}")
        raise e
    else:
        log.info(
            f"REMOVE==========> get_secret_value_response:{get_secret_value_response}"
        )
        return get_secret_value_response


def _p(e):
    """ Internal: pull a projectId from a formatted Resource ID
    TODO: NEED TO DOCUMENT THIS!
    """
    return e[PRI].split("-")[-1].split(",")[-1].split(":")[-1]


def _api(evt, ep, m="GET", d={}, eatable=False):
    """ Internal wraps api access from event
    """
    publickey_template_value = evt[RP].get("PublicKey", "")
    privatekey_template_value = evt[RP].get("PrivateKey", "")
    log.debug(f"**REMOVE** publickey_template_value:{publickey_template_value}")
    log.debug(f"**REMOVE** privatekey_template_value:{privatekey_template_value}")
    if VALID_DEPLOY_KEY:
        pub = DEPLOY_KEY["PUBLIC_KEY"]
        pvt = DEPLOY_KEY["PRIVATE_KEY"]
        log.warning("Override API KEY from deployed Key")
    elif "resolve:secretsmanager" in publickey_template_value:
        log.warning(
            "Detected AWS Secret Manager integration, looking up secret for Atlas API Keys"
        )
        secret_name_public, secret_public_key_name = resolve_secretmanager_ref(
            publickey_template_value
        )
        if secret_name_public is not None:
            log.info(f"secret_name_pubic:{secret_name_public}")
            log.info(f"secret_public_key_name={secret_public_key_name}")
            pub = read_secret(secret_name_public).get(
                secret_public_key_name, "NOT_IN_SECRET"
            )
        else:
            pub = publickey_template_value
            log.info(f"No secret for PublicKey dectected fallback pub={pub}")
            log.info(f"read_secret pub={pub}")

        secret_name_private, secret_private_key_name = resolve_secretmanager_ref(
            publickey_template_value
        )
        if secret_name_private is not None:
            log.info(f"secret_name_private:{secret_name_private}")
            log.info(f"secret_private_key_name={secret_private_key_name}")
            pvt = read_secret(secret_name_private).get(secret_private_key_name, "NOT_IN_SECRET")
            log.info(f"read_secret pvt={pvt}")
        else:
            pvt = privatekey_template_value
            log.info(f"No secret for PrivateKey dectected fallback pvt={pvt}")
    else:
        log.warning(
            "No Secret detected & no DEPLOY_KEY, assume Atlas APIKey values in template request"
        )
        pub = publickey_template_value
        pvt = privatekey_template_value

    return __api(pub, pvt, ep, m, d, eatable)


def __api(pub, pvt, ep, m="GET", d={}, eatable=False):
    """ Internal - wraps all api access
    """
    if m == "GET":
        r = requests.get(ep, auth=HTTPDigestAuth(pub, pvt))
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
    else:
        return j


CREATING_PRI = ""


def create(evt):
    """ Create a new Atlas deployment
    """
    log.info(f"create:evt:{evt}")
    p = evt[RP]
    rt = evt["ResourceType"]
    prj = p["Project"]
    prj["orgId"] = p.get("OrgId", DEPLOY_KEY.get("OrgId"))
    log.info(f"create- try create prj:{prj}")
    pR = _api(evt, f"{MDBg}", m="POST", d=prj)
    resp = {}
    pid = pR["id"]
    prid = f"org:{pR['orgId']},project:{pid}"
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
    # Access List (ip, peering, etc)
    if "AccessList" in p:
        resp["accessList"] = _api(
            evt, f"{MDBg}/{pid}/accessList", m="POST", d=p["AccessList"]
        )
    # Finally, cluster since it takes time
    if "Cluster" in p:
        c = p["Cluster"]
        c.providerName = "AWS"
        ce = f"{MDBg}/{pid}/clusters"
        cr = _api(evt, ce, m="POST", d=c)
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


def update(evt):
    """ Handle the update event
    This needs work
    """
    log.info(f"update:evt:{evt}")
    prj = _api(evt, f"{MDBg}/{_p(evt)}")
    r = {PRI: evt[PRI]}
    r[RESP_DATA] = {}
    pid = prj["id"]
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
    """ Deal with deletes.
    This works well, it will first try delete the cluster and wait
    to clean up the project. It tries to lookup byName and also returns
    SUCCESS when a "bad" ID comes in, probably broker deployment and nothing
    on the MongoDB-side to clean up, so clean up the cfn side of house.
    """
    name = evt[RP]["Name"]
    potential_pid = _p(evt)
    if "LATEST" in potential_pid:
        log.info(f"Broken deployment invalid id format: {potential_pid}. Cleaning up")
        # Note - we just return without error here, this will "clean up" the cfn resource on the AWS-side
        # we don't have anything to clean up on the MongoDB side
        return {
            RESP_DATA: {"Message": "Cleaning up invalid id resource"},
            PRI: evt[PRI],
        }
    prj = _api(evt, f"{MDBg}/{_p(evt)}", eatable=True)
    log.info(f"delete prj:{prj}")
    if prj.get("Code") == "STOP":
        log.info(f"prj was STOP ------->>>> returning OK here, should be doing")
        return {RESP_DATA: prj, PRI: evt[PRI]}

    if "id" not in prj:
        raise Exception(f"No id in prj, this should not ever happen {prj}")
    i = prj["id"]
    if int(prj["clusterCount"]) > 0:
        cd = _api(evt, f"{MDBg}/{i}/clusters/{name}", m="DELETE", eatable=True)
        log.info(f"cluster delete response cd:{cd}")
        # This means that we really did just delete the cluster and should sleep
        # a bit before the api call to delete the group. We might have gotten an "ok"
        # error trying to delete the cluster because it's already been deleted
        try:
            log.warning(f"deleted cluster, sleeping {DS}")
            sleep(DS)
        except Exception as e:
            log.warning(f"exp sleeping:{e}")
    try:
        r = _api(evt, f"{MDBg}/{i}", m="DELETE", eatable=True)
        log.info(f"DELETE project r:{r}")
        return {RESP_DATA: r, PRI: evt[PRI]}
    except Exception as e:
        log.warning(f"ERROR: {e}")
        return {RESP_DATA: {"Error": str(e), PRI: evt[PRI]}}


fns = {"Create": create, "Update": update, "Delete": delete}
VALID_DEPLOY_KEY = False


def validate_deploy_apikey():
    """Check and see if the apikey deployed via the
    environment variables into this function is valid.
    This will also try to lookup the key from an AWS Secret,
    depending on the reference (from cloudformation).
    """
    try:
        log.debug(f"DEPLOY_KEY:{DEPLOY_KEY}")
        try_public = DEPLOY_KEY["PUBLIC_KEY"]
        try_private = DEPLOY_KEY["PRIVATE_KEY"]
        try_org_id = DEPLOY_KEY["ORG_ID"]
        log.debug(f"{try_public} {try_private}")
        public = "INITIAL-VALUE-PUBLIC"
        private = "INITIAL-VALUE-PRIVATE"
        if "resolve:secretsmanager" in try_public:
            secret_name_public, secret_public_key_name = resolve_secretmanager_ref(
                try_public
            )
            log.info(
                f"secret_name_pubic:{secret_name_public}, secret_public_key_name={secret_public_key_name}"
            )
            public = read_secret(secret_name_public).get(
                secret_public_key_name, "NOT_IN_SECRET"
            )
        else:
            public = try_public
            log.debug(
                f"No AWS Secret reference in DEPLOY_KEY['PUBLIC_KEY'] detected, value: {public}"
            )

        if "resolve:secretsmanager" in try_private:
            secret_name_private, secret_private_key_name = resolve_secretmanager_ref(
                try_private
            )
            log.info(
                f"secret_name_private:{secret_name_private}, secret_private_key_name={secret_private_key_name}"
            )
            private = read_secret(secret_name_private).get(
                secret_private_key_name, "NOT_IN_SECRET"
            )
        else:
            private = try_private
            log.debug(
                f"No AWS Secret reference in DEPLOY_KEY['PRIVATE_KEY'] detected, value: {private}"
            )

        if "resolve:secretsmanager" in try_org_id:
            secret_name_org_id, secret_org_id_name = resolve_secretmanager_ref(
                try_org_id
            )
            log.info(
                f"secret_name_org_id:{secret_name_org_id}, secret_org_id_name={secret_org_id_name}"
            )
            org_id = read_secret(secret_name_org_id).get(
                secret_org_id_name, "NOT_IN_SECRET"
            )
            # I'm sorry those are terrible names for variables
        else:
            org_id = try_org_id
            log.debug(
                f"No AWS Secret reference in DEPLOY_KEY['ORG_ID]' detected, value: {org_id}"
            )

        log.debug(f"~~~>  public:{public}, private:{private} org_id:{org_id}")
        # Next line will attempt to GET /groups with the key we just attempted to wrangle with
        # This should return a valid dict[] with the /groups response, if not, or error
        # then VALID_DEPLOY_KEY will set to False and then not override apikey lookup
        # in the _api function above which expects to parse the apikey out of the
        # cloudformation Create/update/delete request event payload.
        org_resp = __api(
            public, private, f"https://cloud.mongodb.com/api/atlas/v1.0/orgs/{org_id}"
        )
        log.debug(f"org_resp={org_resp}")
        VALID_DEPLOY_KEY = (org_resp != None)
        log.warning(
            f"Tried to validate DEPLOY_KEY: VALID_DEPLOY_KEY:{VALID_DEPLOY_KEY}"
        )
        if VALID_DEPLOY_KEY:  # now update local DEPLOY_KEY with resovled values
            DEPLOY_KEY = {
                "PUBLIC_KEY": public,
                "PRIVATE_KEY": private,
                "ORG_ID": org_id,
            }
            log.debug(f"Update DEPLOY_KEY={DEPLOY_KEY}")
        else:
            log.debug(f"Did NOT, yes, 'NOT' Update DEPLOY_KEY={DEPLOY_KEY}")
    except Exception as e:
        log.error(e)
        log.warning(f"ERROR: {e}")


def lambda_handler(evt, ctx):
    log.info(f"got evt {evt}")
    rd = {}
    try:
        # lookup name of right function and call it, create/update/delete
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
    log.info(f"test_entrypoint! does it work? {evt} {ctx}")
    cfnresponse.send(
        evt, ctx, cfnresponse.FAILED, {"error": "Not implemented, yet"}, None
    )
