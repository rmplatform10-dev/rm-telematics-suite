import math

def move_towards(lat, lon, heading_deg, distance_m):
    R=6371000; d=distance_m/R; brg=math.radians(heading_deg)
    lat1=math.radians(lat); lon1=math.radians(lon)
    lat2=math.asin(math.sin(lat1)*math.cos(d)+math.cos(lat1)*math.sin(d)*math.cos(brg))
    lon2=lon1+math.atan2(math.sin(brg)*math.sin(d)*math.cos(lat1),math.cos(d)-math.sin(lat1)*math.sin(lat2))
    return math.degrees(lat2),math.degrees(lon2)

def crc_xor(data):
    cs=0
    for b in data: cs^=b
    return cs
