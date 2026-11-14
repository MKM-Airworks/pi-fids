def dimensions(body):
    if body.startswith(b'\x89PNG\r\n\x1a\n') and len(body)>=24 and body[12:16]==b'IHDR':
        return int.from_bytes(body[16:20],'big'),int.from_bytes(body[20:24],'big')
    if body.startswith(b'\xff\xd8'):
        pos=2
        while pos+4<=len(body):
            if body[pos]!=255:return None
            while pos<len(body) and body[pos]==255:pos+=1
            if pos>=len(body):return None
            marker=body[pos];pos+=1
            if marker in (0xd9,0xda):return None
            if marker in (0x01,0xd8) or 0xd0<=marker<=0xd7:continue
            if pos+2>len(body):return None
            size=int.from_bytes(body[pos:pos+2],'big')
            if size<2 or pos+size>len(body):return None
            if marker in (0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf):
                if size<8:return None
                return int.from_bytes(body[pos+5:pos+7],'big'),int.from_bytes(body[pos+3:pos+5],'big')
            pos+=size
    return None
