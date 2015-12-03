只要改动脚本中的ImagesMap和 EMMC_CAPACITY, 
1.	
  EMMC_CAPACITY 可以联系jun,liu 获得， Jun 从Teleweb 的log 中得到的是以扇区为单位的X, 
   则新项目的XXX_mkfactory.py 中的
   EMMC_CAPACITY=long(X*EMMC_BLOCK_SIZE)
2.
ImagesMap  是lable 到 filename 的映射表，可以根据项目的Name Rules 和rawprogram0.xml 
