"""
Libsmashhit.so tweak tool/file patcher

This uses a very similar archiecture as the classic patch.py or tweak tool but
doesn't provide a GUI for it and is a bit cleaner, though not by much.

To add a patch, create a function that accepts (patcher, params) and then add it
to the right patch table.
"""

import struct

class Patcher:
    """
    A thing we can use to patch a file, in this case libsmashhit.so
    """
    
    def __init__(self, path):
        """
        Initialise the patching utility
        """
        
        self.f = open(path, "rb+")
    
    def __del__(self):
        """
        When we are done with the file
        """
        
        self.f.close()
    
    def patch(self, location, data):
        """
        Write some data to the file at the given location
        """
        
        self.f.seek(location, 0)
        self.f.write(data)
    
    def peek(self, location, amount):
        """
        Peek a certian amount of data from a specific location
        """
        
        self.f.seek(location, 0)
        return self.f.read(amount)

def _patch_const_mov_instruction_arm64(old, value):
    """
    Patch something like mov r0, #0x10 to mov r0, #value
    """
    
    mask = 0b11100000111111110001111100000000
    
    old = old & (~mask)
    
    last = (value & 0b111) << 29
    first = ((value >> 3) & 0b11111111) << 16
    new = last | first
    
    return (old | new)

def _patch_const_subs_instruction_arm64(old, value):
    """
    Patch something like subs r0, r1, #0x10 to subs r0, r1, #value
    """
    
    mask = 0b00000000111111000011111100000000
    
    old = old & (~mask)
    
    last = (value & 0b111111) << 18
    first = ((value >> 6) & 0b111111) << 8
    new = last | first
    
    return (old | new)

def _patch_v142_v143_arm64_antitamper(patcher, params):
    """
    Patch antitamper (this is generally required)
    """
    
    patcher.patch(0x47130, b"\x1f\x20\x03\xd5")
    patcher.patch(0x474b8, b"\x3e\xfe\xff\x17")
    patcher.patch(0x47464, b"\x3a\x00\x00\x14")
    patcher.patch(0x47744, b"\x0a\x00\x00\x14")
    patcher.patch(0x4779c, b"\x1f\x20\x03\xd5")
    patcher.patch(0x475b4, b"\xff\xfd\xff\x17")
    patcher.patch(0x46360, b"\x13\x00\x00\x14")

def _patch_v142_v143_arm64_premium(patcher, params):
    """
    Patch permium
    """
    
    patcher.patch(0x5ace0, b"\x1f\x20\x03\xd5")
    patcher.patch(0x598cc, b"\x14\x00\x00\x14")
    patcher.patch(0x59720, b"\xa0\xc2\x22\x39")
    patcher.patch(0x58da8, b"\x36\x00\x00\x14")
    patcher.patch(0x57864, b"\xbc\x00\x00\x14")
    patcher.patch(0x566ec, b"\x04\x00\x00\x14")

def _patch_v142_v143_arm64_lualib(patcher, params):
    """
    Partially reenable lua's package, io and os modules in scripts
    """
    
    patcher.patch(0xa71b8, b"\xe0\x03\x13\xaa") # Preserve param_1
    patcher.patch(0xa71c8, b"\xb8\x0e\x00\x14") # Chain to luaopen_package
    patcher.patch(0xaaef4, b"\xe0\x03\x13\xaa") # Preserve param_1
    patcher.patch(0xaaf08, b"\xb1\xf0\xff\x17") # Chain to luaopen_io
    patcher.patch(0xa748c, b"\xe0\x03\x13\xaa") # Preserve param_1
    patcher.patch(0xa74a0, b"\xd1\xfe\xff\x17") # Chain to luaopen_os
    patcher.patch(0xa7004, b"\xa0\x00\x80\x52") # Set return to 5 (2 + 1 + 1 + 1 = 5)
    patcher.patch(0xa7010, b"\xc0\x03\x5f\xd6") # Make sure last is return (not really needed)

def _patch_v142_v143_arm64_encryption(patcher, params):
    """
    Nop out the save file encryption functions
    """
    
    patcher.patch(0x567e8, b"\xc0\x03\x5f\xd6")
    patcher.patch(0x5672c, b"\xc0\x03\x5f\xd6")

def _patch_v142_v143_arm64_balls(patcher, params):
    """
    Patch the number of starting balls
    """
    
    value = params[0] if len(params) > 0 else None
    
    if (not value):
        return ["You didn't put in a value for how many balls you want to start with. Balls won't be patched!"]
    
    value = int(value)
    
    # Somehow, this works.
    d = struct.unpack(">I", patcher.peek(0x57cf4, 4))[0]
    patcher.patch(0x57cf4, struct.pack(">I", _patch_const_mov_instruction_arm64(d, value)))
    patcher.patch(0x57ff8, struct.pack("<I", value))

def _patch_v142_v143_arm64_smashhitlabads(patcher, params):
    """
    Enable the Smash Hit Lab Ads mod service
    """
    
    value = params[0] if len(params) > 0 else ""
    
    if (len(value) != 5):
        return ["The mod ID should be five base64 characters."]
    
    value = value.encode('utf-8')
    
    patcher.patch(0x2129a0, b"http://smashhitlab.000webhostapp.com/\x00")
    patcher.patch(0x2129c8, b"ads.php?id=" + value + b"&x=\x00")

def _patch_v142_v143_arm64_savekey(patcher, params):
    """
    Change the encryption key used to obfuscate savegames
    """
    
    value = params[0] if len(params) > 0 else ""
    msg = []
    
    if (not value):
        msg.append("The encryption key will be set to Smash Hit's default key, 5m45hh1t41ght, since you did not set one.")
        value = "5m45hh1t41ght"
    
    key = value.encode('utf-8')
    
    if (len(key) >= 24):
        msg.append("Your encryption key is longer than 23 bytes, so it has been truncated.")
        key = key[:23]
    
    patcher.patch(0x1f3ca8, key + (b"\x00" * (24 - len(key))))
    
    if (msg):
        return msg

def _patch_v142_v143_arm64_vertical(patcher, params):
    """
    Patch to allow running in vertical resolutions
    """
    
    patcher.patch(0x46828, b"\x47\x00\x00\x14") # Patch an if (gWidth < gHeight)
    patcher.patch(0x4693c, b"\x71\x00\x00\x14") # Another if ...
    patcher.patch(0x46a48, b"\x1f\x20\x03\xd5")

def _patch_v142_v143_arm64_fov(patcher, params):
    """
    Set the feild of view for all cameras in the game
    """
    
    value = params[0] if len(params) > 0 else None
    
    if (not value):
        return ["You didn't put in a value for the FoV you want. FoV won't be patched!"]
    
    patcher.patch(0x1c945c, struct.pack("<f", float(value)))

def _patch_v142_v143_arm64_dropballs(patcher, params):
    """
    Set the number of balls to drop when a obstacle is hit.
    
    I'm unsure if Yorshex or OL Epic would like this more...
    """
    
    value = params[0] if len(params) > 0 else None
    
    if (not value):
        return ["You didn't put in a value for how many balls you want to drop when you hit on something. Dropping balls won't be patched!"]
    
    value = int(value)
    
    # Patch the number of balls to subtract from the score
    d = struct.unpack(">I", patcher.peek(0x715f0, 4))[0]
    patcher.patch(0x715f0, struct.pack(">I", _patch_const_subs_instruction_arm64(d, value)))
    
    # Patch the number of balls to drop
    d = struct.unpack(">I", patcher.peek(0x71624, 4))[0]
    patcher.patch(0x71624, struct.pack(">I", _patch_const_mov_instruction_arm64(d, value)))
    
    # This changes from "cmp w23,#0xa" to "cmp w23,w1" so that we don't
    # need to make a specific patch for the comparision.
    patcher.patch(0x7162c, b"\xff\x02\x01\x6b")

def _patch_v142_v143_arm64_checkpoints(patcher, params):
    
    value = params[0] if len(params) > 0 else None
    
    if (not value):
        return ["You didn't put in a value for how many checkpoints you want. Checkpoints won't be patched!"]
    
    value = int(value) + 1
    
    # This seems to be the number of rendered segments
    d = struct.unpack(">I", patcher.peek(0x799e8, 4))[0]
    patcher.patch(0x799e8, struct.pack(">I", _patch_const_mov_instruction_arm64(d, value)))
    
    # Don't exactly know what this is for, but I think it's pointers to the meshes
    # by default it's 0x98 large (0x98 / 0x8 = 19) so it seems like there are 19 entries
    # by default
    d = struct.unpack(">I", patcher.peek(0x78700, 4))[0]
    patcher.patch(0x78700, struct.pack(">I", _patch_const_mov_instruction_arm64(d, (value + 6) * 8)))
    
    # This is in an unused function but I will patch it anyways.
    d = struct.unpack(">I", patcher.peek(0x58010, 4))[0]
    patcher.patch(0x58010, struct.pack(">I", _patch_const_mov_instruction_arm64(d, value)))
    
    # Get the highscores even if the checkpoint is above cp12
    patcher.patch(0x57c18, b"\x1f\x20\x03\xd5")
    patcher.patch(0x57c44, b"\x1f\x20\x03\xd5")
    
    # In Player::reportCheckpoint(int index) we need to report regardless...
    patcher.patch(0x57bb0, b"\x1f\x20\x03\xd5")
    
    # Force loading level if the level index isn't zero
    patcher.patch(0x57c7c, b"\x20\x00\x00\x51")
    patcher.patch(0x57c84, b"\x1f\x00\x00\x71")
    patcher.patch(0x57c88, b"\x40\x03\x00\x54")

def _patch_v142_v143_arm64_segmentrealpaths(patcher, params):
    patcher.patch(0x2119f8, b"\x00")

def _patch_v142_v143_arm64_realpaths(patcher, params):
    patcher.patch(0x2118e8, b"\x00")
    patcher.patch(0x1f48c0, b"\x00")
    
def _patch_v142_v143_arm64_roomtime(patcher, params):
    value = float(params[0]) if len(params) > 0 else None
    
    if (not value):
        return ["You didn't put in a room length in seconds so it will be set to default."]
        value = 32.0
    
    # Smash Hit normalises the value to the range [0.0, 1.0] so we need to take the inverse
    patcher.patch(0x73f80, struct.pack("<f", 1 / value))

def _patch_v142_v143_arm64_trainingballs(patcher, params):
    """
    Remove ball count limit in training mode
    """
    
    patcher.patch(0x6ba5c, b"\x06\x00\x00\x14")

def _patch_v142_v143_arm64_mglength(patcher, params):
    """
    Make mgLength count properly in multiplayer mode
    """
    
    patcher.patch(0x6b6d4, b"\x1f\x20\x03\xd5")

def _patch_v142_v143_arm64_noclip(patcher, params):
    """
    Disable collision detection for the player
    """
    
    patcher.patch(0x71574, b"\xc0\x03\x5f\xd6")

_LIBSMASHHIT_V142_V143_ARM64_PATCH_TABLE = {
    "antitamper": _patch_v142_v143_arm64_antitamper,
    "premium": _patch_v142_v143_arm64_premium,
    "lualib": _patch_v142_v143_arm64_lualib,
    "encryption": _patch_v142_v143_arm64_encryption,
    "balls": _patch_v142_v143_arm64_balls,
    "smashhitlabads": _patch_v142_v143_arm64_smashhitlabads,
    "savekey": _patch_v142_v143_arm64_savekey,
    "vertical": _patch_v142_v143_arm64_vertical,
    "fov": _patch_v142_v143_arm64_fov,
    "dropballs": _patch_v142_v143_arm64_dropballs,
    "checkpoints": _patch_v142_v143_arm64_checkpoints,
    "segmentrealpaths": _patch_v142_v143_arm64_segmentrealpaths,
    "realpaths": _patch_v142_v143_arm64_realpaths,
    "roomtime": _patch_v142_v143_arm64_roomtime,
    "trainingballs": _patch_v142_v143_arm64_trainingballs,
    "mglength": _patch_v142_v143_arm64_mglength,
    "noclip": _patch_v142_v143_arm64_noclip,
}

def _patch_v142_v143_arm32_antitamper(patcher, params):
    """
    Patch the genuine checks for arm32 v142 and v143
    """
    
    # Skip the non-android_main checksum compare
    patcher.patch(0x353e4, b"\x13\x00\x00\xea")
    
    # Skip sig file loading and compare
    patcher.patch(0x36070, b"\x00\xf0\x20\xe3")
    
    # Skip probabialistic checksum check with chance 1/1000
    patcher.patch(0x3633c, b"\x37\x00\x00\xea")
    
    # Skip the smol one
    patcher.patch(0x36398, b"\xd4\xfe\xff\xea")
    
    # Don't stop main loop when gGenuine == 0
    patcher.patch(0x3649c, b"\x93\xfe\xff\xea")

def _patch_v142_v143_arm32_premium(patcher, params):
    """
    Really basic patch for premium on arm32, maybe it works fully or not, idk
    """
    
    # One of my favourite jank hacks of all time, just constantly sets premium
    # to true if it isnt set :P
    # streq  r3,[r0,#this->premium]
    patcher.patch(0x47d9c, b"\xe8\x37\x80\x05")

def _patch_v142_v143_arm32_lualib(patcher, params):
    """
    Allow loading the os, io and package lua libs. To do this we basically merge
    the fuctions for loading multipule lua libs together. On armv7 this is
    easier since there are instructions for higher level stack operations which
    we change just change.
    """
    
    # Start with luaopen_base
    # return count = 2
    
    # Need to allocate the registers properly because some functions use many
    # of them
    patcher.patch(0x910cc, b"\xf8\x4f\x2d\xe9")
    
    # Need to change setting return value to setting it back to lua context
    patcher.patch(0x91240, b"\x04\x00\xa0\xe1")
    
    # Jump to the start of the next register function (without stmdb)
    # also return count += 1 for luaopen_io
    patcher.patch(0x91244, b"\x0f\x00\x00\xea")
    
    # Change setting return value to preserving param_1 for next call
    patcher.patch(0x9154c, b"\x04\x00\xa0\xe1")
    
    # Jumping to start of luaopen_package
    # Should also add 1 to total retval at this point (we're at 4)
    patcher.patch(0x91550, b"\xf3\x0c\x00\xea")
    
    # Kick the ass of stmdb here :D
    patcher.patch(0x94928, b"\x00\xf0\x20\xe3")
    
    # Now of course we preserve param_1
    patcher.patch(0x94b80, b"\x04\x00\xa0\xe1")
    
    # Anddd jump to luaopen_os
    # (also our total retval should now be 5)
    patcher.patch(0x94b84, b"\x3a\xf1\xff\xea")
    
    # Now we've got everything and we can edit the retval to be 5 and also
    # change ldmia to load all of the old register values properly. We should
    # also kill the annoying stmdb that appears for some reason to be a nop.
    patcher.patch(0x91080, b"\x00\xf0\x20\xe3") # nop out stmdb
    patcher.patch(0x91090, b"\x05\x00\xa0\xe3") # mov r0,#0x5
    patcher.patch(0x91094, b"\xf8\x8f\xbd\xe8") # ldmia sp!,{r3..r11,pc}

def _patch_v142_v143_arm32_encryption(patcher, params):
    """
    Disable save encryption
    """
    
    patcher.patch(0x44e88, b"\x1e\xff\x2f\xe1")
    patcher.patch(0x44dd8, b"\x1e\xff\x2f\xe1")

_LIBSMASHHIT_V142_V143_ARM32_PATCH_TABLE = {
    "antitamper": _patch_v142_v143_arm32_antitamper,
    "premium": _patch_v142_v143_arm32_premium,
    "lualib": _patch_v142_v143_arm32_lualib,
    "encryption": _patch_v142_v143_arm32_encryption,
}

def _patch_v152_arm64_premium(patcher, params):
    """
    Patch premium for the beta version 1.5.2
    """
    
    # tick()
    # This one doesn't seem to cause issues
    patcher.patch(0x116d10, b"\x08\xb0\x08\xb9")
    
    # load()
    # This one overwrites some seemingly unused stores to zero of local vars
    # WARNING causes problem (game crash)
    # patcher.patch(0x118fdc, b"\x20\x00\x80\x52") # mov w0, #0x1
    # patcher.patch(0x118fe4, b"\x80\xc2\x22\x39") # strb this, [x20, #0x8b0]

def _patch_v152_arm64_encryption(patcher, params):
    """
    Disable save file encryption
    """
    
    # Player::decrypt()
    patcher.patch(0x117188, b"\xc0\x03\x5f\xd6")
    
    # Player::encrypt()
    patcher.patch(0x118c9c, b"\xc0\x03\x5f\xd6")

_LIBSMASHHIT_V152_ARM64_PATCH_TABLE = {
    "premium": _patch_v152_arm64_premium,
    "encryption": _patch_v152_arm64_encryption,
}

PATCHES_LIST = {
    "arm32": {
        "1.4.2": _LIBSMASHHIT_V142_V143_ARM32_PATCH_TABLE,
        "1.4.3": _LIBSMASHHIT_V142_V143_ARM32_PATCH_TABLE,
    },
    "arm64": {
        "1.4.2": _LIBSMASHHIT_V142_V143_ARM64_PATCH_TABLE,
        "1.4.3": _LIBSMASHHIT_V142_V143_ARM64_PATCH_TABLE,
        "1.5.2": _LIBSMASHHIT_V152_ARM64_PATCH_TABLE,
    },
    "x86": {},
}

def determine_version(p):
    """
    Take a guess at finding the version of libsmashhit.so to use. Returns in
    (arch, version) pair.
    """
    
    # ARM64 v1.4.2 and v1.4.3
    cand = p.peek(0x1f38a0, 5)
    
    if (cand == b"1.4.2" or cand == b"1.4.3"):
        return ("arm64", cand.decode("utf-8"))
    
    # ARM32 v1.4.2 and v1.4.3
    cand = p.peek(0x1c7608, 5)
    
    if (cand == b"1.4.2" or cand == b"1.4.3"):
        return ("arm32", cand.decode("utf-8"))
    
    # ARM64 v1.5.2
    # Still identifies as 1.4.3 in the so for some reason
    cand = p.peek(0x84099, 5)
    
    if (cand == b"1.4.3"):
        return ("arm64", "1.5.2")
    
    return NotImplemented

def patch_binary(path, patches = {}):
    """
    Patch a binary at the given path with the given patches and their parameters
    """
    
    p = Patcher(path)
    
    # Determine the version of libsmashhit.so that's being patched
    so_type = determine_version(p)
    
    if (so_type == NotImplemented):
        return NotImplemented
    
    arch = so_type[0]
    ver = so_type[1]
    archver_patches = PATCHES_LIST[arch][ver]
    
    print(f"Libsmashhit.so version {ver} on {arch} detected")
    
    # # Verify that all patches we want to make are in this binary
    # for patch_type in patches:
    #     if (patch_type not in archver_patches):
    #         return NotImplemented
    
    # Preform the patches
    all_errors = []
    
    for patch_type in patches:
        print(f"Patching {patch_type} ...")
        if (patch_type in archver_patches):
            errors = archver_patches[patch_type](p, patches[patch_type])
        else:
            errors = [f"Patch {patch_type} does not exist"]
        
        if (errors):
            print(f"The following errors occured while patching {patch_type}:")
            print("\n".join(errors))
            all_errors += errors
    
    return all_errors

def valid_patches(path):
    """
    Get (arch, ver, patches) for a given file
    """
    
    p = Patcher(path)
    
    # Determine the version of libsmashhit.so that's being patched
    so_type = determine_version(p)
    
    if (so_type == NotImplemented):
        return None
    
    # Get patches
    arch = so_type[0]
    ver = so_type[1]
    archver_patches = PATCHES_LIST[arch][ver]
    
    patch_list = []
    
    for p in archver_patches:
        patch_list.append(p)
    
    return (arch, ver, patch_list)

_PL_CACHE = {}

def valid_patches_cached(path):
    """
    Cached version of valid_patches
    """
    
    if (path not in _PL_CACHE):
        _PL_CACHE[path] = valid_patches(path)
    
    return _PL_CACHE[path]

def _parse_patch_string(ps):
    """
    Parse a patch string as if it was given on the cmdline
    """
    
    if ("=" not in ps):
        return (ps, [])
    
    ps = ps.split("=")
    ps[1] = ps[1].split(",")
    
    return ps

def _main():
    import sys
    
    if (len(sys.argv) < 2):
        print(f"Usage: {sys.argv[0]} libsmashhit.so [patch0 patch1=param1,param2 ...]")
        return
    
    if (len(sys.argv) < 3):
        print(f"Please specify at least one patch!")
        return
    
    libpath = sys.argv[1]
    patches = dict([_parse_patch_string(x) for x in sys.argv[2:]])
    
    result = patch_binary(libpath, patches)
    
    if (result == NotImplemented):
        print("Error: Either you specified an invalid patch (most likely) or this version and archiecture combination are not supported by the patch tool!")
    elif (result):
        print("Some patches did not succede")
    else:
        print("Success")

if (__name__ == "__main__"):
    _main()
