#!/usr/bin/env python
#===========================================================================
#
#  Copyright (c) 2015 TCL.
#  Author chunhua.chen 
#
#===========================================================================
#
"""
merge image to factory image

"""

import sys,os
import glob
import struct
import binascii
import  zipfile
from xml.etree import ElementTree as ET

EMMC_BLOCK_SIZE=512
#the emmc capacity should be read from emmc chip
#please check your device  ROM size
EMMC_CAPACITY=long(15269888*EMMC_BLOCK_SIZE)

FACTORY_IMAGE_SIZE=EMMC_CAPACITY
#ImagesMap lable -> filename
ImagesMap = {
        'modem':'N*.mbn',
        'sbl1':'C*.mbn',
        'sbl1bak':'C*.mbn',
        'rpm':'W*.mbn',
        'rpmbak':'W*.mbn',
        'tz':'T*.mbn',
        'tzbak':'T*.mbn',
        'fsg':'S*.mbn',
        'sec':'K*.mbn',
        'aboot':'L*.mbn',
        'abootbak':'L*.mbn',
        'boot':'B*.mbn',
        'recovery':'R*.mbn',
        'system':'Y*.mbn',
        'persist':'J*.mbn',
        'splash':'E*.mbn',
        'tctpersist':'F*.mbn',
        'hdcp':'H*.mbn',
        'cache':'I*.mbn',
        'userdata':'U*.mbn',
        'simlock':'X*.mbn',
        'traceability':'stub.bin',
        'misc':'stub.bin',
        'PrimaryGPT':'O*.mbn',
        'BackupGPT':'G*.mbn',
}


SPARSE_HEADER_MAGIC=0xed26ff3a
ZIP_HEADER_MAGIC=0x04034b50
CHUNK_TYPE_RAW=0xCAC1
CHUNK_TYPE_FILL=0xCAC2
CHUNK_TYPE_DONT_CARE=0xCAC3
CHUNK_TYPE_CRC=0xCAC4

GPT_SIGNATURE_1=0x54524150
GPT_SIGNATURE_2=0x20494645
"""
 GPT Offsets
"""
PROTECTIVE_MBR_SIZE=EMMC_BLOCK_SIZE
HEADER_SIZE_OFFSET=12
HEADER_CRC_OFFSET=16
PRIMARY_HEADER_OFFSET=24
BACKUP_HEADER_OFFSET=32
FIRST_USABLE_LBA_OFFSET=40
LAST_USABLE_LBA_OFFSET=48
PARTITION_ENTRIES_OFFSET=72
PARTITION_COUNT_OFFSET=80
PENTRY_SIZE_OFFSET=84
PARTITION_CRC_OFFSET=88
MIN_PARTITION_ARRAY_SIZE=0x4000
PARTITION_ENTRY_LAST_LBA=40
ENTRY_SIZE=0x080


def usage():
  print "Usage: %s <m|d> <imagedir> <factoryimage> " % sys.argv[0]
  print"""Examples:
  python ~/tools/mkfactoryimage.py m  ~/myprj/Pixi47TMO/appli/vBA4  ~/output/factoryimage_vBA4.bin

  When use the python script in new project, pls modify
  EMMC_CAPACITY
  ImagesMap

  NOTE:
  EMMC_CAPACITY can read  use emmcdl or log of Teleweb
"""
  exit(1)

def CmpPartition(x,y):
  if x['start_byte_hex'] > y['start_byte_hex']:
    return int(1)
  elif x['start_byte_hex'] == y['start_byte_hex']:
    return int(0)
  elif x['start_byte_hex'] < y['start_byte_hex']:
    return int(-1) 

def ParseXML(XMLFile):
  PartitionCollection = []

  root = ET.parse( XMLFile )

  #Create an iterator
  iter = root.getiterator()
  for element in iter:
    if element.tag == 'program':
      if element.keys():
        Partition = {}
        ptype = 0
        for name, value in element.items():
          #print "name %s, value %s." % (name, value)
          if name == 'label' and value == 'BackupGPT':
            ptype = 1
          if name == 'start_byte_hex' and ptype == 0:
            Partition[name] = long(value,0)
          else:
            Partition[name] = value
        #print "partition: %s" % Partition 

        if ptype == 1:
          continue
        PartitionCollection.append(Partition)

  PartitionCollection.sort(cmp=CmpPartition)
  #print "PartitionCollection:%s" % PartitionCollection
  return PartitionCollection


def copy_sparse_image(imgin, imgout, offset, size):
  """
  typedef struct sparse_header {
    uint32_t  magic;              /* 0xed26ff3a */
    uint16_t      major_version;  /* (0x1) - reject images with higher major versions */
    uint16_t      minor_version;  /* (0x0) - allow images with higer minor versions */
    uint16_t      file_hdr_sz;    /* 28 bytes for first revision of the file format */
    uint16_t      chunk_hdr_sz;   /* 12 bytes for first revision of the file format */
    uint32_t      blk_sz;         /* block size in bytes, must be a multiple of 4 (4096) */
    uint32_t      total_blks;     /* total blocks in the non-sparse output image */
    uint32_t      total_chunks;   /* total chunks in the sparse input image */
    uint32_t      image_checksum; /* CRC32 checksum of the original data, counting "don't care" */
                                  /* as 0. Standard 802.3 polynomial, use a Public Domain */
                                  /* table implementation */
  } sparse_header_t;

  typedef struct chunk_header {
    uint16_t      chunk_type;     /* 0xCAC1 -> raw; 0xCAC2 -> fill; 0xCAC3 -> don't care */
    uint16_t      reserved1;
    uint32_t      chunk_sz;       /* in blocks in output image */
    uint32_t      total_sz;       /* in bytes of chunk input file including chunk header and data */
  } chunk_header_t;

  """
  imgin.seek(8,0)
  file_hdr_sz = struct.unpack('<H',imgin.read(struct.calcsize('H')))[0]
  chunk_hdr_sz = struct.unpack('<H',imgin.read(struct.calcsize('H')))[0]
  blk_sz = struct.unpack('<I',imgin.read(struct.calcsize('I')))[0]
  total_blks = struct.unpack('<I',imgin.read(struct.calcsize('I')))[0]
  total_chunks = struct.unpack('<I',imgin.read(struct.calcsize('I')))[0]
  #print "file_hdr_sz:%s chunk_hdr_sz:%s, blk_sz:%s total_blks:%s total_chunks:%s" % (file_hdr_sz, chunk_hdr_sz, blk_sz, total_blks, total_chunks)
  if total_blks * blk_sz > size:
    print("ERROR: %s size(%d) too large in partition(%d)" % (imgin.name, total_blks * blk_sz, size))
    sys.exit(1)

  imgin.seek(file_hdr_sz, 0)
  total_blocks  = long(0)
  for chunk in range(total_chunks):
    #print("chunk...")
    chunk_type = struct.unpack('<H',imgin.read(struct.calcsize('H')))[0]
    reserved1 = struct.unpack('<H',imgin.read(struct.calcsize('H')))[0]
    chunk_sz = struct.unpack('<I',imgin.read(struct.calcsize('I')))[0]
    total_sz  = struct.unpack('<I',imgin.read(struct.calcsize('I')))[0]
    s_sz = struct.calcsize('<HHII')
    if chunk_hdr_sz > s_sz:
      imgin.seek(chunk_hdr_sz-s_sz, 1)
    chunk_data_sz = blk_sz * chunk_sz
    

    if chunk_type == CHUNK_TYPE_RAW:
      if total_sz != chunk_hdr_sz + chunk_data_sz:
        print("ERROR:Bogus chunk size for chunk type Raw")
        sys.exit(1);
      imgout.seek(offset+total_blocks*blk_sz,0)
      imgout.write(imgin.read(chunk_data_sz))
      total_blocks += chunk_sz
    elif chunk_type == CHUNK_TYPE_FILL:
      if total_sz != chunk_hdr_sz + struct.calcsize('<I'):
        print("ERROR:Bogus chunk size for chunk type FILL")
        sys.exit(1);
      fill_val = imgin.read(struct.calcsize('<I'))
      chunk_blk_cnt = chunk_data_sz/blk_sz
      fill_buf = [fill_val]*(blk_sz/struct.calcsize('<I'))
      for i in range(chunk_blk_cnt):
        imgout.seek(offset+total_blocks*blk_sz,0)
        imgout.write(''.join(fill_buf))
        total_blocks += 1
    elif chunk_type == CHUNK_TYPE_DONT_CARE:
      total_blocks += chunk_sz
    elif chunk_type == CHUNK_TYPE_CRC:
      if total_sz != chunk_hdr_sz:
        print("ERROR:Bogus chunk size for chunk type Dont Care")
        sys.exit(1);
      total_blocks += chunk_sz
      imgin.seek(chunk_data_sz, 1)
    else:
      print("ERROR:Unkown chunk type:%x" % chunk_type)
      sys.exit(1);
    if offset + total_blocks*blk_sz > FACTORY_IMAGE_SIZE:
      print("merge all image done")
      imgin.close()
      imgout.close()
      sys.exit(0)

  print("Wrote %d blocks, expected to write %d blocks" % (total_blocks, total_blks))
  pad = offset + total_blocks*blk_sz - imgout.tell()
  if pad > 0:
    print "sparse image end pad"
    zerofile = open('/dev/zero', 'rb')
    imgout.write(zerofile.read(pad))
  elif pad == 0:
    print "sparse image done"
  else:
    print("ERROR: sparse image write failure")
    sys.exit(1);

def partition_parse_gpt_header(buff):
  print("gpt signature2 1:0x%x 0x%x" % (struct.unpack('<I', buff[0:4])[0], struct.unpack('<I',buff[4:8])[0]))
  if struct.unpack('<I', buff[0:4])[0] != GPT_SIGNATURE_2 or struct.unpack('<I',buff[4:8])[0] != GPT_SIGNATURE_1:
    return (int(1),0,0,0,0)
  header_size = struct.unpack('<L',buff[HEADER_SIZE_OFFSET:HEADER_SIZE_OFFSET+4])[0]
  first_usable_lba = struct.unpack('<Q', buff[FIRST_USABLE_LBA_OFFSET:FIRST_USABLE_LBA_OFFSET+8])[0]
  max_partition_count = struct.unpack('<L', buff[PARTITION_COUNT_OFFSET:PARTITION_COUNT_OFFSET+4])[0]
  partition_entry_size = struct.unpack('<L', buff[PENTRY_SIZE_OFFSET:PENTRY_SIZE_OFFSET+4])[0]
  print("header size %d,usable lba 0x%lx, max partition count %d, parition entry size %d" % (header_size, first_usable_lba, max_partition_count, partition_entry_size))
  return (int(0),first_usable_lba, partition_entry_size, header_size, max_partition_count)



def patch_traceability(version, outimg, offset, size):
  """
  patch the traceability partition
  """
  """
  partition offset + 67 is traceability
  """
  offset += 67
  INFO_PTS_MINI_OFFSET=50
  MINIMODE_SFLAG_OFFSET=310
  MINIMODE_SFLAG_MAGIC=0xb4a59687
  outimg.seek(offset+INFO_PTS_MINI_OFFSET, 0)
  outimg.write(struct.pack('%ds' % (len(version)), version))
  outimg.seek(offset+MINIMODE_SFLAG_OFFSET, 0)
  outimg.write(struct.pack('<I', MINIMODE_SFLAG_MAGIC))
 
def patch_misc(outimg, offset, size):
  """
  patch the misc partition
  """
  ffbm='ffbm-01'
  outimg.seek(offset, 0)
  outimg.write(struct.pack('%ds' % (len(ffbm)), ffbm))

def patch_gpt(infile, image):
  """
  patch the gpt for the real emmc
  """
  """ TODO fix me """
  infile.seek(0,0)
  gptImage = infile.read(-1)
  #print("gpt:%s" % gptImage)
  primary_gpt_header = gptImage[EMMC_BLOCK_SIZE:]
  #print("gpt header:%s" % primary_gpt_header)
  (ret,first_usable_lba, partition_entry_size, header_size, max_partition_count) = partition_parse_gpt_header(primary_gpt_header)
  if ret:
    print("GPT: Primary signature invalid cannot write GPT")
    return
  partition_entry_array_size = partition_entry_size * max_partition_count;
  if partition_entry_array_size < MIN_PARTITION_ARRAY_SIZE:
    partition_entry_array_size = MIN_PARTITION_ARRAY_SIZE
  card_size_sec = EMMC_CAPACITY/EMMC_BLOCK_SIZE
  if card_size_sec == 0:
    card_size_sec = 4*1024*1024*2-1

  """ Patching primary header """
  image.seek(EMMC_BLOCK_SIZE+BACKUP_HEADER_OFFSET,0)
  image.write(struct.pack('<q', card_size_sec -1))
  image.seek(EMMC_BLOCK_SIZE+LAST_USABLE_LBA_OFFSET,0)
  image.write(struct.pack('<q', card_size_sec -34))

  """ Find last partition """
  total_part = 0
  while struct.unpack('<B',primary_gpt_header[EMMC_BLOCK_SIZE+total_part*ENTRY_SIZE:EMMC_BLOCK_SIZE+total_part*ENTRY_SIZE+1])[0] != 0:
    total_part+=1
  print("total_part %d" % total_part)

  """ Patching last partition """
  last_part_offset = (total_part - 1) * ENTRY_SIZE + PARTITION_ENTRY_LAST_LBA;
  image.seek(EMMC_BLOCK_SIZE*2+last_part_offset,0)
  image.write(struct.pack('<q', card_size_sec-34))

  """ Updating CRC of the Partition entry array in main gpt headers """
  partition_entry_array_start = EMMC_BLOCK_SIZE*2;
  image.seek(partition_entry_array_start)
  crc_value = (binascii.crc32(image.read(max_partition_count*partition_entry_size))&0xffffffff)
  print("crc value:%s" % crc_value)
  image.seek(EMMC_BLOCK_SIZE+PARTITION_CRC_OFFSET,0)
  image.write(struct.pack('<I', crc_value))

  """ Clearing CRC fields to calculate """
  image.seek(EMMC_BLOCK_SIZE + HEADER_CRC_OFFSET,0)
  image.write(struct.pack('<I', 0))
  image.seek(EMMC_BLOCK_SIZE)
  crc_value = (binascii.crc32(image.read(92))&0xffffffff)
  image.seek(EMMC_BLOCK_SIZE + HEADER_CRC_OFFSET,0)
  image.write(struct.pack('<I', crc_value))

def detect_version(partitions, imagetype, imagedir):
  BOOT_IMAGE_VERSION_OFFSET=0x30
  fn = None
  label = None
  for p in partitions:
    fn = p['filename']
    label = p['label']
    if label != 'boot':
      continue
    if imagetype == 0:
      fn = os.path.join(imagedir,fn)
    else:
      paths = glob.glob(os.path.join(imagedir,ImagesMap[label]))
      if len(paths) > 1:
        print("ERROR: match too many files %s" % paths)
        sys.exit(1)
      if paths:
        fn = paths[0];
      else:
        paths = glob.glob(os.path.join(imagedir,"%s.%s" % (ImagesMap[label][:-4], 'zip')))
        if len(paths) > 1:
          print("ERROR: match too many files %s" % paths)
          sys.exit(1)
        if paths:
          fn = paths[0];
    if not os.path.exists(fn):
      print "ERROR:version detect Could not found the image:%s" % fn
      sys.exit(1)
    else:
      break
  infile = open(fn, 'rb')
  infile.seek(BOOT_IMAGE_VERSION_OFFSET,0)
  vers = struct.unpack("12s", infile.read(12))[0]
  infile.close()
  print("detect versions(%s) in %s" %(vers, fn))
  #print("detect %s %s %s" % (fn[-16:-4], vers[2:5], fn[-14:-11]))
  if imagetype == 0 or vers == fn[-16:-4]:
    return vers[2:5]
  else:
    return fn[-14:-11]

def merge_image(partitions, imagetype, imagedir, image):
  for p in partitions:
    fn = p['filename']
    soffset = p['start_byte_hex']
    size = long(p['num_partition_sectors'])*long(p['SECTOR_SIZE_IN_BYTES'])
    label = p['label']
    if label == 'userdata':
      """
      fix userdata size
      """
      FIX_USERDATA_SIZE = EMMC_CAPACITY-33*EMMC_BLOCK_SIZE - soffset;
      size = long(FIX_USERDATA_SIZE)
    if label == 'traceability':
      """
      fix traceability fn
      """
      version = detect_version(partitions, imagetype, imagedir)
      print("label:%s patch the traceability version(%s) ..." % (label, version))
      patch_traceability(version, image, soffset, size)
      continue
    if label == 'misc':
      print("label:%s patch the misc ...")
      patch_misc(image, soffset, size)
      continue
    if label == 'fsg':
      fn = 'studypara.mbn'
    if not fn:
      print("label:%s padding %s size of zero..." % (label, size))
      zerofile = open('/dev/zero', 'rb')
      image.seek(soffset, 0)
      if (soffset != image.tell()):
        print("ERROR: wrong soffset")
        sys.exit(1)
      image.write(zerofile.read(size))
      zerofile.close()
      continue
    if imagetype == 0:
      fn = os.path.join(imagedir,fn)
    else:
      paths = glob.glob(os.path.join(imagedir,ImagesMap[label]))
      if len(paths) > 1:
        print("ERROR: match too many files %s" % paths)
        sys.exit(1)
      if paths:
        fn = paths[0];
      else:
        paths = glob.glob(os.path.join(imagedir,"%s.%s" % (ImagesMap[label][:-4], 'zip')))
        if len(paths) > 1:
          print("ERROR: match too many files %s" % paths)
          sys.exit(1)
        if paths:
          fn = paths[0];
    if not os.path.exists(fn):
      print "WARN:Could not found the image:%s" % fn
      continue
    infile = open(fn, 'rb')
    magic = struct.unpack('<I',infile.read(struct.calcsize('I')))[0]
    print("label:%s magic:0x%x" % (label, magic))
    print os.popen('file %s' % infile.name, 'r').read()
    print("write %s to factoryimage..." % fn)
    if magic == ZIP_HEADER_MAGIC:
      infile.close();
      input_zip = zipfile.ZipFile(fn, 'r');
      i = 0;
      for n in input_zip.namelist():
        i += 1;
        if i > 1:
          print("ERROR:too many file in zipfile:%s" % fn)
          sys.exit(1)
        infile = input_zip.open(n);
      inmagic = struct.unpack('<I',infile.read(struct.calcsize('I')))[0]
      print("label:%s magic:0x%x in %s" % (label, inmagic, fn))
      print("write %s in %s to factoryimage..." % (n, fn))
      infile.close();
      if  inmagic == SPARSE_HEADER_MAGIC:
        print("ERROR: not support")
        sys.exit(1)
      image.seek(soffset, 0)
      if (soffset != image.tell()):
        print("ERROR: seek fail wrong soffset")
        sys.exit(1)
      infile = input_zip.open(n)
      count = input_zip.getinfo(n).file_size
      if count >  size:
        print("ERROR: image %s(%d) too large in partition size(%d) " % ( infile.name, count, size))
        sys.exit(1)
      blksize = 32*1024*1024
      while count > 0:
        if count > blksize:
          image.write(infile.read(blksize))
          count -= blksize
        else:
          image.write(infile.read(count))
          count = 0;
      input_zip.close()
    elif  magic == SPARSE_HEADER_MAGIC:
      print("unsparse image...")
      infile.seek(0,0)
      copy_sparse_image(infile,image, soffset, size)
    else:
      infile.seek(0,0)
      image.seek(soffset, 0)
      if (soffset != image.tell()):
        print("ERROR: seek fail wrong soffset")
        sys.exit(1)
      image.write(infile.read(size))
      if infile.tell() > size:
        print("ERROR: %s size(%d) too large in partition(%d)" % (infile.name, infile.tell(), size))
        sys.exit(1)
      if label == 'PrimaryGPT':
        patch_gpt(infile, image)
    infile.close()
  #end

def dump_image(image, partitions):
  for p in partitions:
    fn = p['filename']
    soffset = p['start_byte_hex']
    size = long(p['num_partition_sectors'])*long(p['SECTOR_SIZE_IN_BYTES'])
    label = p['label']
    if not fn:
      print("LABEL:%s empty" % label)
      continue
    print("LABEL:%s dump..." % label)
    if label == 'userdata':
      FIX_USERDATA_SIZE = EMMC_CAPACITY-33*EMMC_BLOCK_SIZE - soffset;
      size = long(FIX_USERDATA_SIZE)
    outimg = open(fn,'wb')
    image.seek(soffset, 0)
    outimg.write(image.read(size))
    outimg.close()


def main(argv):
  if len(argv) != 3:
    usage()
  
  cmd = 'm'
  if argv[0] == 'd':
    cmd = 'd'
  elif argv[0] == 'm':
    cmd = 'm'
  else:
    usage()

  imagedir = argv[1]
  imagetype = 0
  rawprogram_path = os.path.join(imagedir,"rawprogram0.xml")
  if not os.path.exists(rawprogram_path):
    paths = glob.glob(os.path.join(imagedir,"P*.mbn"))
    if paths and os.path.exists(paths[0]):
      rawprogram_path = paths[0]
      imagetype = 1
  #print "rawprogram:%s" % rawprogram_path
  if not os.path.exists(rawprogram_path):
    print 'Not found the rawprogram file in the imagedir:%s' % imagedir
    exit(1)

  partitions = ParseXML(rawprogram_path)
  if cmd == 'm':
    image = open(argv[2], 'w+b')
    merge_image(partitions, imagetype, imagedir, image)
    image.close()
  else:
    image = open(argv[2], 'rb')
    dump_image(image, partitions)
    image.close()

if __name__ == "__main__":
  main(sys.argv[1:])
