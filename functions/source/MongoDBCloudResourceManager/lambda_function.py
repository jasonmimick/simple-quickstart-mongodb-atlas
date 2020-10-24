import cfnresponse
import logging
import sys
import requests
from requests.auth import HTTPDigestAuth
from time import sleep
import traceback

log = logging.getLogger()
log.setLevel(logging.DEBUG)
_l=log.info
_lw=log.warn
DS=30       # Sleep 30 seconds after cluster delete before deleting project
RESP_DATA="Data"
RP="ResourceProperties"
RT="RequestType"
PRI="PhysicalResourceId"
MDBg="https://cloud.mongodb.com/api/atlas/v1.0/groups"
PRID="X"
CS="connectionStrings"
OK_DELETE_ERRORCODES= [
    "GROUP_NOT_FOUND",
    "NOT_IN_GROUP",
    "CLUSTER_ALREADY_REQUESTED_DELETION",
    "INVALID_GROUP_ID"
]

def _p(e):
    return e[PRI].split('-')[-1].split(',')[-1].split(':')[-1]


def _api(evt,ep,m="GET",d={},eatable=False):
    pub=evt[RP].get('PublicKey','')
    pvt=evt[RP].get('PrivateKey','')
    if (m=="GET"):
        r=requests.get(ep,auth=HTTPDigestAuth(pub,pvt))
    elif (m=="DELETE"):
        r = requests.delete(ep,auth=HTTPDigestAuth(pub,pvt))
    elif (m == "POST"):
        r = requests.post(ep,auth=HTTPDigestAuth(pub,pvt),headers={"Content-Type":"application/json"},json=d)
    else:
        raise Exception(f"bad m:{m}")

    j=r.json()
    _l(f"_api m:{m} json:{j}")
    if "error" in j:
        if (eatable and (j['errorCode'] in OK_DELETE_ERRORCODES)):
            _lw(f"OK ERROR DETECTED: Error: {j}")
            return { "Code" : "STOP", "Message" : "Ok error response from MongoDB Cloud detected." }
        else:
            _lw(traceback.print_exc())
            raise Exception(j)
    else:
        return j

CREATING_PRI=""
def create(evt):
    _l(f"create:evt:{evt}")
    p = evt[RP]
    rt = evt['ResourceType']
    prj = p['Project']
    prj['orgId'] = p['OrgId']
    pR = _api(evt, f"{MDBg}",m="POST", d=prj)
    resp = {}
    pid=pR['id']
    prid = f"org:{pR['orgId']},project:{pid}"
    resp[PRI] = prid
    CREATING_PRI=prid
    # Database Users
    _d = []
    for dbu in p.get('DatabaseUsers'):
      dbu['groupId']=pid
      dbr = _api(evt, f"{MDBg}/{pid}/databaseUsers",m="POST", d=dbu)
      _d.append(dbr)
    # Cloud Provider Access
    ecpa = _api(evt,f"{MDBg}/{pid}/cloudProviderAccess",m="POST",d={"providerName":"AWS"})
    for k in ecpa:
      resp[f"cloudProviderAccess-{k}"] = ecpa[k]
    # Access List (ip, peering, etc)
    if 'AccessList' in p:
      resp["accessList"]=_api(evt,f"{MDBg}/{pid}/accessList",m="POST",d=p['AccessList'])
    # Finally, cluster since it takes time
    if "Cluster" in p:
      c=p['Cluster']
      c.providerName = "AWS"
      ce=f"{MDBg}/{pid}/clusters"
      cr=_api(evt, ce,m="POST", d=c)
      resp["SrvHost"]=wait_for_cluster(evt,ce,5)
    resp["project"]=_api(evt,f"{MDBg}/{pid}")
    return {RESP_DATA:resp,PRI:prid}


def wait_for_cluster(evt,ep,m=1):
    _l(f"{m}min wait cluster")
    sleep(m*60)
    c=_api(evt,ep)['results'][0]
    if c.get('stateName')=="IDLE":
        return c.get('srvAddress')
    else:
        return wait_for_cluster(evt,ep,1)

def update(evt):
    _l(f"update:evt:{evt}")
    prj=_api(evt,f"{MDBg}/{_p(evt)}")
    r={PRI:evt[PRI]}
    r[RESP_DATA]={}
    i=prj['id']
    if int(prj['clusterCount'])>0:
        c=_api(evt, f"{MDBg}/{i}/clusters/{evt[RP]['Name']}")
        r[RESP_DATA]["SrvHost"]=c.get('srvAddress',c.get('stateName'))
    e = _api(evt,f"{MDBg}/{i}/cloudProviderAccess")
    for k in e['awsIamRoles'][0]:
        r[RESP_DATA][f"cloudProviderAccess-{k}"] = e['awsIamRoles'][0][k]
    if 'accessList' in p['AccessList']:
        resp["accessList"]=_api(evt,f"{MDBg}/{pid}/accessList",m="POST",d=p['Plan']['accessList'])
    return r

def delete(evt):
    name=evt[RP]["Name"]
    potential_pid=_p(evt)
    if "LATEST" in potential_pid:
        _l(f"Broken deployment invalid id format: {potential_pid}. Cleaning up")
        # Note - we just return without error here, this will "clean up" the cfn resource on the AWS-side
        # we don't have anything to clean up on the MongoDB side
        return {RESP_DATA:{"Message":"Cleaning up invalid id resource"},PRI:evt[PRI]}
    prj = _api(evt,f"{MDBg}/{_p(evt)}",eatable=True)
    _l(f"delete prj:{prj}")
    if prj.get('Code')=="STOP":
        _l(f"prj was STOP ------->>>> returning OK here, should be doing")
        return {RESP_DATA:prj,PRI:evt[PRI]}

    if not 'id' in prj:
        raise Exception(f"No id in prj, this should not ever happen {prj}")
    i=prj['id']
    if int(prj['clusterCount'])>0:
        cd=_api(evt, f"{MDBg}/{i}/clusters/{name}", m="DELETE",eatable=True)
        _l(f"cluster delete response cd:{cd}")
        # This means that we really did just delete the cluster and should sleep
        # a bit before the api call to delete the group. We might have gotten an "ok"
        # error trying to delete the cluster because it's already been deleted
        try:
            _lw(f"deleted cluster, sleeping {DS}")
            sleep(DS)
        except Exception as e:
            _lw(f"exp sleeping:{e}")
    try:
        r=_api(evt, f"{MDBg}/{i}", m="DELETE",eatable=True)
        _l(f"DELETE project r:{r}")
        return {RESP_DATA:r,PRI:evt[PRI]}
    except Exception as e:
        _lw(f"ERROR: {e}")
        return {RESP_DATA:{"Error": str(e),PRI:evt[PRI]}}

fns={'Create':create,'Update':update,'Delete':delete}

def lambda_handler(evt, ctx):
    _l(f"got evt {evt}")
    rd={}
    try:
        # lookup name of right function and call it, create/update/delete
        rd=fns[evt[RT]](evt)
        _l(f"rd:{rd}")
        if PRI not in rd:
            log.error(f"No PRI in rsp")
            raise Exception(rd)
        cfnresponse.send(evt,ctx,cfnresponse.SUCCESS,rd[RESP_DATA],rd[PRI])
    except Exception as error:
        log.error(error)
        cfnresponse.send(evt,ctx,cfnresponse.FAILED,{'error':str(error)},CREATING_PRI)
