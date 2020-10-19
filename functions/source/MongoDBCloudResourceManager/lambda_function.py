import logging
import sys
import cfnresponse
import requests
from requests.auth import HTTPDigestAuth
from time import sleep
import traceback

log = logging.getLogger()
log.setLevel(logging.DEBUG)
_l=log.info
_lw=log.warn
DS=20
RD="Data"
RP="ResourceProperties"
RT="RequestType"
PRI="PhysicalResourceId"
MDBg="https://cloud.mongodb.com/api/atlas/v1.0/groups"
RT_DPL="Custom::AtlasDeployment"
RT_DBU="Custom::AtlasDatabaseUser"
PRID="X"
CS="connectionStrings"
OK_DELETE_ERRORCODES= [
    "GROUP_NOT_FOUND",
    "NOT_IN_GROUP",
    "CLUSTER_ALREADY_REQUESTED_DELETION"
]
OK_EXCEPTION_STOP=False

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
        raise Execption(f"bad m:{m}")
    j=r.json()
    _l(f"_api m:{m} json:{j}")
    if "error" in j:
        if (eatable and (j['errorCode'] in OK_DELETE_ERRORCODES)):
            _lw(f"OK ERROR DETECTED: Error: {j}")
            OK_EXCEPTION_STOP=True
            return j
        else:
            OK_EXCEPTION_STOP=False
            _lw(traceback.print_exc())
            raise Exception(j)
    else:
        OK_EXCEPTION_STOP=False
        return j

CREATING_PRI=""
def create(evt):
    _l(f"create:evt:{evt}")
    p = evt[RP]
    rt = evt['ResourceType']
    prj = p['Plan']['project']
    prj['orgId'] = p['OrgId']
    if rt==RT_DPL:
      pR = _api(evt, f"{MDBg}",m="POST", d=prj)
    else:
      pR = _api(evt, f"{MDBg}/byName/{evt[RP]['Name']}")
    resp = {}
    pid=pR['id']
    prid = f"org:{pR['orgId']},project:{pid}"
    resp[PRI] = prid
    CREATING_PRI=prid
    # Database Users
    _d = []
    for dbu in p['Plan'].get('databaseUsers'):
      dbu['groupId']=pid
      dbr = _api(evt, f"{MDBg}/{pid}/databaseUsers",m="POST", d=dbu)
      _d.append(dbr)
    # Cloud Provider Access
    ecpa = _api(evt,f"{MDBg}/{pid}/cloudProviderAccess",m="POST",d={"providerName":"AWS"})
    for k in ecpa:
      resp[f"cloudProviderAccess-{k}"] = ecpa[k]
    # Access List (ip, peering, etc)
    if 'accessList' in p['Plan']:
      resp["accessList"]=_api(evt,f"{MDBg}/{pid}/accessList",m="POST",d=p['Plan']['accessList'])
    # Finally, cluster since it takes time
    if "cluster" in p['Plan']:
      c=p['Plan']['cluster']
      ce=f"{MDBg}/{pid}/clusters"
      cr=_api(evt, ce,m="POST", d=c)
      resp["SrvHost"]=w4c(evt,ce,5)
    resp["project"]=_api(evt,f"{MDBg}/{pid}")
    return {RD:resp,PRI:prid}
def w4c(evt,ep,m=1):
    _l(f"{m}min wait cluster")
    sleep(m*60)
    c=_api(evt,ep)['results'][0]
    if c.get('stateName')=="IDLE":
        return c.get('srvAddress')
    else:
        return w4c(evt,ep,1)
def update(evt):
    _l(f"update:evt:{evt}")
    prj=_api(evt,f"{MDBg}/{_p(evt)}")
    r={PRI:evt[PRI]}
    r[RD]={}
    i=prj['id']
    if int(prj['clusterCount'])>0:
        c=_api(evt, f"{MDBg}/{i}/clusters/{evt[RP]['Name']}")
        r[RD]["SrvHost"]=c.get('srvAddress',c.get('stateName'))
    e = _api(evt,f"{MDBg}/{i}/cloudProviderAccess")
    for k in e['awsIamRoles'][0]:
        r[RD][f"cloudProviderAccess-{k}"] = e['awsIamRoles'][0][k]
    if 'accessList' in p['Plan']:
        resp["accessList"]=_api(evt,f"{MDBg}/{pid}/accessList",m="POST",d=p['Plan']['accessList'])
    return r

def delete(evt):
    name=evt[RP]["Name"]
    prj, cont = _api(evt,f"{MDBg}/{_p(evt)}",eatable=True)
    if OK_EXCEPTION_STOP:
      return {RD:prj,PRI:evt[PRI]}
    i=prj['id']
    if int(prj['clusterCount'])>0:
        cd, cont=_api(evt, f"{MDBg}/{i}/clusters/{name}", m="DELETE",eatable=True)
        _l("cluster delete response cd:{cd}")
        # This means that we really did just delete the cluster and should sleep
        # a bit before the api call to delete the group. We might have gotten an "ok"
        # error trying to delete the cluster because it's already been deleted
        if not OK_EXCEPTION_STOP:
            try:
                _lw(f"deleted cluster, sleeping {DS}")
                sleep(DS)
            except Exception as e:
                 _lw(f"exp sleeping:{e}")
    try:
        r=_api(evt, f"{MDBg}/{i}", m="DELETE",eatable=True)
        _l(f"DELETE project cont:{cont} r:{r}")
        return {RD:r,PRI:evt[PRI]}
    except Exception as e:
        _lw("fERROR: {e}")
        return {RD:e,PRI:evt[PRI]}

fns={'Create':create,'Update':update,'Delete':delete}

def lambda_handler(evt, ctx):
    _l(f"got evt {evt}")
    rd={}
    try:
        rd=fns[evt[RT]](evt)
        _l(f"rd:{rd}")
        if PRI not in rd:
            log.error(f"No PRI in rsp")
            raise Exception(rd)
        cfnresponse.send(evt,ctx,cfnresponse.SUCCESS,rd[RD],rd[PRI])
    except Exception as error:
        log.error(error)
        cfnresponse.send(evt,ctx,cfnresponse.FAILED,{'error':str(error)},CREATING_PRI)
