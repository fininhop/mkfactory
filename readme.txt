
Usage: ./mkfactoryimage.py <m|d> <imagedir> <factoryimage> 
Examples:
  python ~/tools/mkfactoryimage.py m  ~/myprj/Pixi47TMO/appli/vBA4  ~/output/factoryimage_vBA4.bin

  When use the python script in new project, pls modify
  EMMC_CAPACITY
  ImagesMap

  NOTE:
  EMMC_CAPACITY can read  use emmcdl or log of Teleweb



THANKS!!!

只要改动脚本中的ImagesMap和 EMMC_CAPACITY, 
1.	
  EMMC_CAPACITY 可以联系jun,liu 获得， Jun 从Teleweb 的log 中得到的是以扇区为单位的X, 
   则新项目的XXX_mkfactory.py 中的
   EMMC_CAPACITY=long(X*EMMC_BLOCK_SIZE)
2.
ImagesMap  是lable 到 filename 的映射表，可以根据项目的Name Rules 和rawprogram0.xml 


GOOGLE TRANSLATION
"
As long as the changes in the script ImageMaps and EMMC_CAPACITY,
1.
   EMMC_CAPACITY can contact jun, liu get, Jun from the Teleweb's log is the sector as a unit of X,
    The new project in XXX_mkfactory.py
    EMMC_CAPACITY = long (X * EMMC_BLOCK_SIZE)
2.
ImagesMap is a lable to filename mapping table that can be based on the project's Name Rules and rawprogram0.xml
"
