import logging
import sys
from botocore.vendored import requests
from botocore.vendored.requests.auth import HTTPDigestAuth
import cfnresponse
from time import sleep

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
def _p(e):
    return e[PRI].split('-')[-1].split(',')[-1].split(':')[-1]

def _api(evt,ep,m="GET",d={}):
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
        raise Exception(f"{j['error']},{j['errorCode']},{j['detail']}")
    return j
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
    resp["project"]=pR
    pid=pR['id']
    prid = f"org:{pR['orgId']},project:{pid}"
    resp[PRI] = prid
    if rt==RT_DPL:
        ecpa = _api(evt,f"{MDBg}/{pid}/cloudProviderAccess",m="POST",d={"providerName":"AWS"})
        for k in ecpa:
          resp[f"cloudProviderAccess-{k}"] = ecpa[k]
    if rt==RT_DBU:
      _d = []
      for dbu in p['Plan'].get('databaseUsers'):
        _l(f"dbu: {dbu}")
        dbu['groupId']=pid
        dbr = _api(evt, f"{MDBg}/{pid}/databaseUsers",m="POST", d=dbu)
        _d.append(dbr)
      resp["databaseUsers"] = _d
      if pR['clusterCount']>0:
        cR=_api(evt,f"{MDBg}/{pid}/clusters")
        resp["SrvHost"]=st=cR['results'][0]['stateName']
        if CS in cR['results'][0]:
          resp["SrvHost"]=cR['results'][0][CS].get('standardSrv',st)
    if "cluster" in p['Plan']:
        c=p['Plan']['cluster']
        cr=_api(evt, f"{MDBg}/{pid}/clusters",m="POST", d=c)
        resp["cluster"]=cr
    return {RD:resp,PRI:prid}
def update(evt):
    _l(f"update:evt:{evt}")
    prj=_api(evt,f"{MDBg}/{_p(evt)}")
    r={RD:{"project":prj},PRI:evt[PRI]}
    i=prj['id']
    if int(prj['clusterCount'])>0:
        c=_api(evt, f"{MDBg}/{i}/clusters/{evt[RP]['Name']}")
        r[RD]["SrvHost"]=c[CS].get('standardSrv',c['stateName'])
        r[RD]["cluster"]=c
    e = _api(evt,f"{MDBg}/{i}/cloudProviderAccess")
    for k in e['awsIamRoles']:
        r[RD][f"cloudProviderAccess-{k}"] = e['awsIamRoles'][0][k]
    return r
def delete(evt):
    pid=_p(evt)
    name=evt[RP]["Name"]
    try:
      prj=_api(evt,f"{MDBg}/{pid}")
    except Exception as exp:
      _l(f"got {exp} tring /byName")
      prj=_api(evt, f"{MDBg}/byName/{evt[RP]['Name']}")
    if int(prj['clusterCount'])>0:
        cd=_api(evt, f"{MDBg}/{pid}/clusters/{name}", m="DELETE")
        _lw(f"deleted cluster, sleeping {DS}")
        try:
            sleep(DS)
        except Exception as e:
            _lw(f"exp sleeping:{e}")
    r=_api(evt, f"{MDBg}/{prj['id']}", m="DELETE")
    return {RD:r,PRI:evt[PRI]}
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
        cfnresponse.send(evt,ctx,cfnresponse.FAILED,{'error':str(error)})
