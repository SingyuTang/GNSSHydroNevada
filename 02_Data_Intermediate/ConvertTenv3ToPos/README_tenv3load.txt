
Brief documentation for .tenv3 format enhanced with load prediction triplets.

NGL now provides time series files enhanced to include the predictions of some geophysical loads, including non-tidal atmospheric loading, non-tidal ocean loading, GRACE-inferred hydrological loading, and large reservoirs.

The files are similar to the .tenv3 files except that they include extra columns with the 3-component displacement predictions from the loading models.
The text files are found here:  http://geodesy.unr.edu/gps_timeseries/tenv3_loadpredictions/xxxx.tenv3
where xxxx is the station 4-character ID.
These files are updated periodically. 

col 1-23:  See .tenv3 README file here: http://geodesy.unr.edu/gps_timeseries/README_tenv3.txt (without station latitude, longitude and height)
col 24-26: east, north and up component of non-tidal atmospheric loading displacements  (NTAL)
col 27-29: east, north and up components of non-tidal ocean loading displacements  (NTOL)
col 30-32: east, north and up components of hydrological model load displacements (HYDL)
col 33-35: east, north, and up components from GRACE mascon-based loading displacements (MASC)
col 36-38: Displacements from lake water changes from water gauging stations in the western U.S., Dakotas and Montana, and several big lakes Near Lake Manitoba.
col 39-41: Displacements from lake water changes from satellite altimetry worldwide (Gaastra et al., in prep.)

The predictions in columns 21-29 are from ESMGFZ (http://rz-vm115.gfz-potsdam.de:8080/repository, Dill and Dobslaw, JGR, 2013; Dill, 2008)
Their hydrological model is from from 24-hourly terrestrial water storage global hydrological model LSDM forced by ECMWF operational atmospheric data
produced by IERS Associated Product Centre Deutsches GeoForschungsZentrum (GFZ) Potsdam. LSDM masses are given on a regular 0.5x0.5 degrees.
http://rz-vm115.gfz-potsdam.de:8080/repository/entry/show?entryid=dadb0121-32f0-4eaa-a3ec-b5f37860e4d1

We get the NTAL, NTOL, HYDL measurements at each GPS station by fitting a spline to GFZ's lat, lon grids using their program "extractlatlon_bicubintp".

Plots of the vertical component of the processed GPS time series data with and without the loading prediction removed are provided at 
http://geodesy.unr.edu/tsplots/IGS14/IGS14/load_plots/xxxx_load.png
where xxxx is the station 4-character ID.

In the plots (e.g., http://geodesy.unr.edu/tsplots/IGS14/IGS14/load_plots/P143_load.png) NTAL stands for non-tidal atmospheric loading, NTOL for non-tidal oceanic loading, MASC for GRACE mascon based loading prediction.
These plots show the degree to which the loading models explain the GPS vertical displacements.

Note that prior to 2002 GRACE mascon data are unavailable so the model is based on an extrapolation based on the mean rate and seasonal oscillation of the GRACE data from the 1st GRACE datum to April 2022.

