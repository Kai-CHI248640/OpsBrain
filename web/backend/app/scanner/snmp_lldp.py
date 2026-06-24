import asyncio
import ipaddress
from typing import Optional

from logging_setup import get_logger
from pysnmp.hlapi.v3.asyncio import (
    getCmd, nextCmd, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity
)

log = get_logger(__name__)

# LLDP OID Constants (Standard IEEE 802.1AB)
LLDP_LOCAL_CHASSIS_ID = "1.3.6.1.4.1.9.9.23.1.3.1.1" # Cisco specific, wait standard is .1.0.8802.1.1.2.1.3.2.1.4
# General LLDP MIBs
LLDP_LOCAL_PORT_DESC = "1.0.8802.1.1.2.1.3.7.1.4" 
LLDP_NEIGHBOR_CHASSIS_ID = "1.0.8802.1.1.2.1.4.1.1.5"
LLDP_NEIGHBOR_PORT_ID = "1.0.8802.1.1.2.1.4.1.1.7"
LLDP_NEIGHBOR_SYSTEM_NAME = "1.0.8802.1.1.2.1.4.1.1.9"

# Cisco CDP OID (Cisco proprietary)
CDP_NEIGHBOR_TABLE = "1.3.6.1.4.1.9.9.23.1.2.1.1"

async def get_lldp_neighbors_snmp(host: str, community: str = "public") -> list:
    """
    Uses SNMP to query LLDP neighbors from a device.
    Returns list of dicts: {'local_port': str, 'remote_chassis': str, 'remote_port': str, 'remote_name': str}
    """
    neighbors = []
    try:
        # Walk the LLDP remote system table
        # OID: 1.0.8802.1.1.2.1.4.1.1 (lldpRemTable)
        # We need to walk .1.0.8802.1.1.2.1.4.1.1.5 (lldpRemChassisIdSubtype) and others
        
        # Simplified approach: Use standard LLDP OIDs
        # lldpRemLocalPortNum (1.0.8802.1.1.2.1.4.1.1.3)
        # lldpRemChassisId (1.0.8802.1.1.2.1.4.1.1.5)
        # lldpRemPortId (1.0.8802.1.1.2.1.4.1.1.7)
        # lldpRemSystemName (1.0.8802.1.1.2.1.4.1.1.9)
        
        base_oid = "1.0.8802.1.1.2.1.4.1.1"
        
        iterator = nextCmd(
            CommunityData(community, mpModel=0),
            UdpTransportTarget((host, 161), timeout=2, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False
        )
        
        async for errorIndication, errorStatus, errorIndex, varBinds in iterator:
            if errorIndication:
                log.error(f"SNMP error: {errorIndication}")
                break
            elif errorStatus:
                log.error(f"SNMP error status: {errorStatus.prettyPrint()}")
                break
            
            neighbor = {}
            local_port_num = ""
            
            for varBind in varBinds:
                oid_str = str(varBind[0])
                value = str(varBind[1])
                
                # Extract local port number (index)
                if ".3.1.3" in oid_str: # lldpRemLocalPortNum
                    local_port_num = value
                elif ".5.1.5" in oid_str: # lldpRemChassisId
                    neighbor['remote_chassis'] = value
                elif ".7.1.7" in oid_str: # lldpRemPortId
                    neighbor['remote_port'] = value
                elif ".9.1.9" in oid_str: # lldpRemSystemName
                    neighbor['remote_name'] = value
            
            if local_port_num and neighbor.get('remote_chassis'):
                neighbor['local_port_num'] = local_port_num
                neighbors.append(neighbor)
                
    except Exception as e:
        log.error(f"LLDP SNMP failed for {host}: {e}")
    
    return neighbors

async def get_cdp_neighbors_snmp(host: str, community: str = "public") -> list:
    """
    Uses SNMP to query CDP neighbors (Cisco specific).
    """
    neighbors = []
    try:
        # CDP Cache Table
        # 1.3.6.1.4.1.9.9.23.1.2.1.1.4 - cdpCacheAddress (IP)
        # 1.3.6.1.4.1.9.9.23.1.2.1.1.5 - cdpCacheDeviceId (Name)
        # 1.3.6.1.4.1.9.9.23.1.2.1.1.6 - cdpCacheDevicePort (Port)
        # 1.3.6.1.4.1.9.9.23.1.2.1.1.7 - cdpCachePlatform (Model)
        
        base_oid = "1.3.6.1.4.1.9.9.23.1.2.1.1"
        
        iterator = nextCmd(
            CommunityData(community, mpModel=0),
            UdpTransportTarget((host, 161), timeout=2, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False
        )
        
        cache = {}
        
        async for errorIndication, errorStatus, errorIndex, varBinds in iterator:
            if errorIndication or errorStatus:
                break
            
            for varBind in varBinds:
                oid_str = str(varBind[0])
                value = str(varBind[1])
                
                # Parse index from OID (e.g. 1.3.6.1.4.1.9.9.23.1.2.1.1.4.1.16 -> index is 1.16)
                parts = oid_str.split(base_oid + ".")[-1].split(".")
                idx = ".".join(parts)
                
                if idx not in cache:
                    cache[idx] = {}
                
                if ".1.4." in oid_str: # cdpCacheAddress
                    cache[idx]['ip'] = value
                elif ".1.5." in oid_str: # cdpCacheDeviceId
                    cache[idx]['name'] = value
                elif ".1.6." in oid_str: # cdpCacheDevicePort
                    cache[idx]['port'] = value
                elif ".1.7." in oid_str: # cdpCachePlatform
                    cache[idx]['platform'] = value
        
        # Convert index-based cache to neighbor list
        # Index format is usually: local_port_if_index.remote_index
        for idx, data in cache.items():
            # Simplified: assume local port is the first part of index
            local_port = idx.split(".")[0] if "." in idx else "unknown"
            neighbors.append({
                'local_port': local_port,
                'remote_name': data.get('name', 'unknown'),
                'remote_port': data.get('port', 'unknown'),
                'remote_ip': data.get('ip', ''),
                'remote_platform': data.get('platform', '')
            })
            
    except Exception as e:
        log.error(f"CDP SNMP failed for {host}: {e}")
    
    return neighbors

async def query_device_lldp(host: str, community: str = "public") -> dict:
    """
    Full query of a single device for LLDP neighbors.
    Returns structured data including neighbor list.
    """
    try:
        # Get basic info
        sys_info = await get_snmp_sysinfo(host, community)
        
        # Get neighbors
        neighbors = await get_lldp_neighbors_snmp(host, community)
        
        return {
            "host": host,
            "name": sys_info.get("name", host),
            "vendor": sys_info.get("vendor", "unknown"),
            "neighbors": neighbors,
            "neighbor_count": len(neighbors)
        }
    except Exception as e:
        return {"host": host, "error": str(e)}

async def get_snmp_sysinfo(host: str, community: str = "public") -> dict:
    """Get system info via SNMP."""
    try:
        oids = {
            "sysName": "1.3.6.1.2.1.1.5.0",
            "sysDescr": "1.3.6.1.2.1.1.1.0",
        }
        result = {}
        for name, oid in oids.items():
            errorIndication, errorStatus, _, varBinds = await getCmd(
                CommunityData(community, mpModel=0),
                UdpTransportTarget((host, 161), timeout=2),
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )
            if not errorIndication and not errorStatus:
                result[name] = str(varBinds[0][1])
        
        # Identify vendor from sysDescr
        descr = result.get("sysDescr", "").lower()
        if "cisco" in descr:
            result["vendor"] = "cisco"
        elif "huawei" in descr:
            result["vendor"] = "huawei"
        elif "h3c" in descr:
            result["vendor"] = "h3c"
        else:
            result["vendor"] = "unknown"
            
        return result
    except Exception as e:
        return {"error": str(e)}
