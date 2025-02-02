"""
Create template json model files for Feelpp/HiFiMagnet simu
From a yaml definition file of an insert

Inputs:
* method : method of solve, with feelpp cfpdes, getdp...
* time: stationnary or transient case
* geom: geometry of solve, 3D or Axi
* model: physic solved, thermic, thermomagnetism, thermomagnetism-elastic
* phytype: if the materials are linear or non-linear
* cooling: what type of cooling, mean or grad

Output: 
* tmp.json

App setup is stored in a json file that defines
the mustache template to be used.

Default path:
magnetsetup.json
mustache templates
"""

# TODO check for unit consistency
# depending on Length base unit

from typing import List, Optional

import sys
import os
import json
import yaml
import math

from python_magnetgeo import Helix
from python_magnetgeo import Ring
from python_magnetgeo import InnerCurrentLead
from python_magnetgeo import OuterCurrentLead
from python_magnetgeo import Insert
from python_magnetgeo import python_magnetgeo

class appenv():
    
    def __init__(self, debug: bool = False):
        self.url_api: str = None
        self.yaml_repo: Optional[str] = None
        self.mesh_repo: Optional[str] = None
        self.template_repo: Optional[str] = None

        from decouple import Config, RepositoryEnv
        envdata = RepositoryEnv("settings.env")
        data = Config(envdata)
        if debug:
            print("appenv:", RepositoryEnv("settings.env").data)

        self.url_api = data.get('URL_API')
        if 'TEMPLATE_REPO' in envdata:
            self.template_repo = data.get('TEMPLATE_REPO')

    def template_path(self, debug: bool = False):
        """
        returns template_repo
        """
        if not self.template_repo:
            default_path = os.path.dirname(os.path.abspath(__file__))
            template_repo = os.path.join(default_path, "templates")

        if debug:
            print("appenv/template_path:", template_repo)
        return template_repo

def loadconfig():
    """
    Load app config (aka magnetsetup.json)
    """

    default_path = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(default_path, 'magnetsetup.json'), 'r') as appcfg:
        magnetsetup = json.load(appcfg)
    return magnetsetup

def loadtemplates(appenv: appenv, appcfg: dict , method_data: List[str], linear: bool=True, debug: bool=False):
    """
    Load templates into a dict

    method_data:
    method
    time
    geom
    model
    cooling

    """
    
    [method, time, geom, model, cooling] = method_data
    template_path = os.path.join(appenv.template_path(), method, geom, model)
    
    cfg_model = appcfg[method][time][geom][model]["cfg"]
    json_model = appcfg[method][time][geom][model]["model"]
    if linear:
        conductor_model = appcfg[method][time][geom][model]["conductor-linear"]
    else:
        if geom == "3D": 
            json_model = appcfg[method][time][geom][model]["model-nonlinear"]
        conductor_model = appcfg[method][time][geom][model]["conductor-nonlinear"]
    insulator_model = appcfg[method][time][geom][model]["insulator"]
    
    fcfg = os.path.join(template_path, cfg_model)
    if debug:
        print("fcfg:", fcfg, type(fcfg))
    fmodel = os.path.join(template_path, json_model)
    fconductor = os.path.join(template_path, conductor_model)
    finsulator = os.path.join(template_path, insulator_model)
    if model != 'mag':
        cooling_model = appcfg[method][time][geom][model]["cooling"][cooling]
        flux_model = appcfg[method][time][geom][model]["cooling-post"][cooling]
        stats_T_model = appcfg[method][time][geom][model]["stats_T"]
        stats_Power_model = appcfg[method][time][geom][model]["stats_Power"]

        fcooling = os.path.join(template_path, cooling_model)
        if debug:
            print("fcooling:", fcooling, type(fcooling))
        fflux = os.path.join(template_path, flux_model)
        fstats_T = os.path.join(template_path, stats_T_model)
        fstats_Power = os.path.join(template_path, stats_Power_model)

    material_generic_def = ["conductor", "insulator"]
    if time == "transient":
        material_generic_def.append("conductor-nosource") # only for transient with mqs

    dict = {
        "cfg": fcfg,
        "model": fmodel,
        "conductor": fconductor,
        "insulator": finsulator,
        "material_def" : material_generic_def
    }

    if model != 'mag':
        dict = Merge(dict, {"cooling": fcooling, "flux": fflux, "stats": [fstats_T, fstats_Power] })

    if check_templates(dict):
        pass

    return dict    

def check_templates(templates: dict):
    """
    check if template file exist
    """
    print("\n\n=== Checking Templates ===")
    for key in templates:
        if isinstance(templates[key], str):
            print(key, templates[key])
            with open(templates[key], "r") as f: pass

        elif isinstance(templates[key], str):
            for s in templates[key]:
                print(key, s)
                with open(s, "r") as f: pass
    print("==========================\n\n")
    
    return True

def query_db(appenv: appenv, mtype: str, name: str, debug: bool = False):
    """
    Get object from magnetdb
    """

    import requests
    import requests.exceptions
    # import ast

    r = requests.get(url= appenv.url_api + '/' + mtype + '/mdata/' + name )
    if debug: print("request:", r)
    if (r.status_code == requests.codes.ok):
        if debug: print("request:", r.text)
        mdata = json.loads(r.text)
        if debug:
            print("query_db/mdata:", mdata)
        # confdata = ast.literal_eval(r.text)
        return mdata
    else:
        print("failed to retreive %s from db" % name)
        list_mtype_db(appenv, mtype)
        print("available requested mtype in db are: ", list_mtype_db(appenv, mtype))
        sys.exit(1)

def list_mtype_db(appenv: appenv, mtype: str, debug: bool = False):
    """
    List object of mtype stored in magnetdb
    """

    import requests
    import requests.exceptions
    # import ast

    names = []
    if mtype in ["Helix", "Bitter", "Supra"]:
        mtype = "mpart"
    r = requests.get(url= appenv.url_api + '/' + mtype + 's/' )
    if debug:
        print("url=%s", appenv.url_api)
        print("request(url=%s):" % (appenv.url_api + '/' + mtype + 's/'), r)
    if (r.status_code == requests.codes.ok):
        data = json.loads(r.text)
        # data = ast.literal_eval(r.text)
        if debug:
            print("list_mtype_db:", data)
        return [ d["name"] for d in data ]
    pass

def Merge(dict1, dict2):
    """
    Merge dict1 and dict2 to form a new dictionnary
    """

    res = {**dict1, **dict2}
    return res    

def load_object(appenv: appenv, datafile: str, debug: bool = False):
    """
    Load object props
    """

    if appenv.yaml_repo:
        print("Look for %s in %s" % (datafile, appenv.yaml_repo))
    else:
        print("Look for %s in workingdir %s" % (datafile, os.getcwd()))
    with open(datafile, 'r') as cfgdata:
            confdata = json.load(cfgdata)
    return confdata

def load_object_from_db(appenv: appenv, mtype: str, name: str, debug: bool = False):
    """
    Load object props from db
    """

    if not mtype in ["msite", "magnet", "Helix", "Bitter", "Supra", "material"]:
        raise("query_bd: %s not supported" % mtype)
    
    return query_db(appenv, mtype, name, debug)

def convert_data(distance_unit, confdata, gdata, h, mu0):
    """
    Convert the input in distance_unit ('meter' or millimeter).
    """
    
    import warnings
    from pint import UnitRegistry, Unit, Quantity

    # Ignore warning for pint
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        Quantity([])

    # Pint configuration
    ureg = UnitRegistry()
    ureg.default_system = 'SI'
    ureg.autoconvert_offset_to_baseunit = True

    (NHelices, NRings, NChannels, Nsections, R1, R2, Z1, Z2, Zmin, Zmax, Dh, Sh) = gdata

    confdata_convert = confdata.copy()

    for mtype in ["Helix", "Ring", "Lead"]:
        for i in range(len(confdata_convert[mtype])):
            
            # ThermalConductivity : W/m/K --> W/distance_unit/K
            confdata_convert[mtype][i]["material"]["ThermalConductivity"] = Quantity( confdata_convert[mtype][i]["material"]["ThermalConductivity"], ureg.watt / ureg.meter / ureg.kelvin ).to( ureg.watt / ureg.Unit(distance_unit) / ureg.kelvin ).magnitude
            
            # Young : kg/m/s --> kg/distance_unit/s
            confdata_convert[mtype][i]["material"]["Young"] = Quantity( confdata_convert[mtype][i]["material"]["Young"], ureg.kilogram / ureg.meter / ureg.second ).to( ureg.kilogram / ureg.Unit(distance_unit) / ureg.second ).magnitude
            
            # VolumicMass : kg/m3 --> kg/distance_unit**3
            confdata_convert[mtype][i]["material"]["VolumicMass"] = Quantity( confdata_convert[mtype][i]["material"]["VolumicMass"], ureg.kilogram / ureg.meter**3 ).to( ureg.kilogram / ureg.Unit(distance_unit)**3 ).magnitude
            
            # ElectricalConductivity : S/m --> S/distance_unit
            confdata_convert[mtype][i]["material"]["ElectricalConductivity"] = Quantity( confdata_convert[mtype][i]["material"]["ElectricalConductivity"], ureg.siemens / ureg.meter ).to( ureg.siemens / ureg.Unit(distance_unit) ).magnitude

            # Rpe : kg/m/s --> kg/distance_unit/s
            confdata_convert[mtype][i]["material"]["Rpe"] = Quantity( confdata_convert[mtype][i]["material"]["Rpe"], ureg.kilogram / ureg.meter / ureg.second ).to( ureg.kilogram / ureg.Unit(distance_unit) / ureg.second ).magnitude

    # Distances : mm -> distance_unit
    R1_convert   = Quantity( R1, ureg.millimeter ).to( ureg.Unit(distance_unit) ).magnitude.tolist()
    R2_convert   = Quantity( R2, ureg.millimeter ).to( ureg.Unit(distance_unit) ).magnitude.tolist()
    Z1_convert   = Quantity( Z1, ureg.millimeter ).to( ureg.Unit(distance_unit) ).magnitude.tolist()
    Z2_convert   = Quantity( Z2, ureg.millimeter ).to( ureg.Unit(distance_unit) ).magnitude.tolist()
    Zmin_convert = Quantity( Zmin, ureg.millimeter ).to( ureg.Unit(distance_unit) ).magnitude.tolist()
    Zmax_convert = Quantity( Zmax, ureg.millimeter ).to( ureg.Unit(distance_unit) ).magnitude.tolist()

    # Surfaces : mm2 -> distance_unit2
    Dh_convert   = Quantity( Dh, ureg.millimeter**2 ).to( ureg.Unit(distance_unit)**2 ).magnitude.tolist()
    Sh_convert   = Quantity( Sh, ureg.millimeter**2 ).to( ureg.Unit(distance_unit)**2 ).magnitude.tolist()

    gdata_convert = (NHelices, NRings, NChannels, Nsections, R1_convert, R2_convert,
                    Z1_convert, Z2_convert, Zmin_convert, Zmax_convert, Dh_convert, Sh_convert)

    # MagnetPermeability of vacuum : H/m --> H/distance_unit
    mu0_convert = Quantity( mu0, ureg.henry / ureg.meter ).to( ureg.henry / ureg.Unit(distance_unit) ).magnitude

    # Convection coefficients : W/m2/K --> W/distance_unit**2/K
    h_convert = Quantity( h, ureg.watt / ureg.meter**2 / ureg.kelvin ).to( ureg.watt / ureg.Unit(distance_unit)**2 / ureg.kelvin ).magnitude

    return confdata_convert, gdata_convert, h_convert, mu0_convert

def create_cfg(cfgfile:str, name: str, nonlinear: bool, jsonfile: str, template: str, method_data: List[str], debug: bool=False):
    """
    Create a cfg file
    """
    print("create_cfg %s from %s" % (cfgfile, template) )

    dim = 2
    if method_data[2] == "3D":
        dim = 3

    linear = ""
    if nonlinear:
        linear = "nonlinear"

    mesh = name + ".med" # "med", "gmsh", "hdf5" aka "json"

    data = {
        "dim": dim,
        "method": method_data[0],
        "model": method_data[3],
        "geom": method_data[2],
        "time": method_data[1],
        "linear": linear,
        "name": name,
        "jsonfile": jsonfile,
        "mesh": mesh,
        "scale": 0.001,
        "partition": 0
    }
    
    mdata = entry_cfg(template, data, debug)
    if debug:
        print("create_cfg/mdata=", mdata)

    with open(cfgfile, "x") as out:
        out.write(mdata)
    
    pass

def create_params(gdata: tuple, h: float, mu0: float, method_data: List[str], debug: bool=False):             # TODO : better manage of h
    """
    Return params_dict, the dictionnary of section \"Parameters\" for JSON file.
    """

    # TODO: length data are written in mm should be in SI instead
    #unit_Length = 1.e-3
    #unit_Area = 1.e-6

    (NHelices, NRings, NChannels, Nsections, R1, R2, Z1, Z2, Zmin, Zmax, Dh, Sh) = gdata
    
    # Tini, Aini for transient cases??
    params_data = { 'Parameters': []}

    # for cfpdes only
    if method_data[0] == "cfpdes" and method_data[3] == "thmagel" :
        params_data['Parameters'].append({"name":"bool_laplace", "value":"1"})
        params_data['Parameters'].append({"name":"bool_dilatation", "value":"1"})

    # TODO : initialization of parameters with cooling model

    params_data['Parameters'].append({"name":"Tinit", "value":293})
    params_data['Parameters'].append({"name":"mu0", "value":mu0})         # TODO : better manage of mu0
    params_data['Parameters'].append({"name":"h", "value":h})             # TODO : better manage of h
    params_data['Parameters'].append({"name":"Tw", "value":290.671})
    params_data['Parameters'].append({"name":"dTw", "value":12.74})
    
    # params per cooling channels
    # h%d, Tw%d, dTw%d, Dh%d, Sh%d, Zmin%d, Zmax%d :

    # TODO: length data are written in mm should be in SI instead
    for i in range(NHelices+1):
        params_data['Parameters'].append({"name":"h%d" % i, "value":h})             # TODO : better manage of h
        params_data['Parameters'].append({"name":"Tw%d" % i, "value":290.671})
        params_data['Parameters'].append({"name":"dTw%d" % i, "value":12.74})
        params_data['Parameters'].append({"name":"Zmin%d" % i, "value":Zmin[i]})
        params_data['Parameters'].append({"name":"Zmax%d" % i, "value":Zmax[i]})
        params_data['Parameters'].append({"name":"Sh%d" % i, "value":Sh[i]})
        params_data['Parameters'].append({"name":"Dh%d" % i, "value":Dh[i]})

    # init values for U (Axi specific)
    if method_data[2] == "Axi":
        for i in range(NHelices):
            for j in range(Nsections[i]):
                params_data['Parameters'].append({"name":"U_H%d_Cu%d" % (i+1, j+1), "value":"1"})
        for i in range(NHelices):
            for j in range(Nsections[i]):
                params_data['Parameters'].append({"name":"N_H%d_Cu%d" % (i+1, j+1), "value":Nsections[i]})
    
    # TODO: CG: U_H%d%
    # TODO: HDG: U_H%d% if no ibc

    return params_data

def create_materials(gdata: tuple, idata: Optional[List], confdata: dict, templates: dict, method_data: List[str], debug: bool = False):
    # TODO loop for Plateau (Axi specific)
    materials_dict = {}

    fconductor = templates["conductor"]
    finsulator = templates["insulator"]

    (NHelices, NRings, NChannels, Nsections, R1, R2, Z1, Z2, Zmin, Zmax, Dh, Sh) = gdata

    # Loop for Helix
    for i in range(NHelices):
        if method_data[2] == "3D":
            mdata = entry(fconductor, Merge({'name': "H%d_Cu" % (i+1), 'marker': "H%d_Cu" % (i+1)}, confdata["Helix"][i]["material"]) , debug)
            materials_dict["H%d_Cu" % (i+1)] = mdata["H%d_Cu" % (i+1)]

            # TODO deal with Glue/Kaptons
            if idata:
                for item in idata:
                    if item(0) == "Glue":
                        name = "Isolant%d" % (i+1)
                        mdata = entry(finsulator, Merge({'name': name, 'marker': "H%d_Isolant" % (i+1)}, confdata["Helix"][i]["insulator"]), debug)
                    else:
                        name = "Kaptons%d" % (i+1)
                        kapton_dict = { "name": "[\"Kapton%1%\"]", "index1": "0:%d" % item(1)}
                        mdata = entry(finsulator, Merge({'name': name, 'marker': kapton_dict}, confdata["Helix"][i]["insulator"]), debug)
                    materials_dict[name] = mdata[name]
        else:
            # section j==0:  treated as insulator in Axi
            mdata = entry(finsulator, Merge({'name': "H%d_Cu%d" % (i+1, 0)}, confdata["Helix"][i]["material"]), debug)
            materials_dict["H%d_Cu%d" % (i+1, 0)] = mdata["H%d_Cu%d" % (i+1, 0)]
        
            # load conductor template
            for j in range(1,Nsections[i]+1):
                mdata = entry(fconductor, Merge({'name': "H%d_Cu%d" % (i+1, j)}, confdata["Helix"][i]["material"]), debug)
                materials_dict["H%d_Cu%d" % (i+1, j)] = mdata["H%d_Cu%d" % (i+1, j)]

            # section j==Nsections+1:  treated as insulator in Axi
            mdata = entry(finsulator, Merge({'name': "H%d_Cu%d" % (i+1, Nsections[i]+1)}, confdata["Helix"][i]["material"]), debug)
            materials_dict["H%d_Cu%d" % (i+1, Nsections[i]+1)] = mdata["H%d_Cu%d" % (i+1, Nsections[i]+1)]

    # loop for Rings
    for i in range(NRings):
        if method_data[2] == "3D":
            mdata = entry(fconductor, Merge({'name': "R%d" % (i+1)}, confdata["Ring"][i]["material"]), debug)
        else:
            mdata = entry(finsulator, Merge({'name': "R%d" % (i+1)}, confdata["Ring"][i]["material"]), debug)
        materials_dict["R%d" % (i+1)] = mdata["R%d" % (i+1)]
        
    # Leads: 
    if method_data[2] == "3D" and confdata["Lead"]:
        mdata = entry(fconductor, Merge({'name': "iL1"}, confdata["Lead"][0]["material"]), debug)
        materials_dict["iL1"] = mdata["iL1"]

        mdata = entry(fconductor, Merge({'name': "oL2"}, confdata["Lead"][1]["material"]), debug)
        materials_dict["oL2"] = mdata["oL2"]

    return materials_dict

def create_bcs(args,
               boundary_meca: List, 
               boundary_maxwell: List,
               boundary_electric: List,
               boundary_Therm_Neu: List,
               boundary_Electric_Neu: List,
               gdata: tuple, confdata: dict, templates: dict, method_data: List[str], debug: bool = False):

    print("create_bcs from templates")
    electric_bcs_dir = { 'boundary_Electric_Dir': []} # name, value, vol
    electric_bcs_neu = { 'boundary_Electric_Neu': []} # name, value
    thermic_bcs_rob = { 'boundary_Therm_Robin': []} # name, expr1, expr2
    thermic_bcs_neu = { 'boundary_Therm_Neu': []} # name, value
    meca_bcs_dir = { 'boundary_Meca_Dir': []} # name, value
    maxwell_bcs_dir = { 'boundary_Maxwell_Dir': []} # name, value
    
    (NHelices, NRings, NChannels, Nsections, R1, R2, Z1, Z2, Zmin, Zmax, Dh, Sh) = gdata
    
    if args.model != 'mag':
        fcooling = templates["cooling"]
    
        for i in range(NChannels):
            # load insulator template for j==0
            mdata = entry(fcooling, {'i': i}, debug)
            thermic_bcs_rob['boundary_Therm_Robin'].append( Merge({"name": "Channel%d" % i}, mdata["Channel%d" % i]) )

    for bc in boundary_meca:
        meca_bcs_dir['boundary_Meca_Dir'].append({"name":bc, "value":"{0,0}"})

    for bc in boundary_maxwell:
        if method_data[2] == "3D":
            maxwell_bcs_dir['boundary_Maxwell_Dir'].append({"name":bc, "value":"{0,0}"})
        else:
            maxwell_bcs_dir['boundary_Maxwell_Dir'].append({"name":bc, "value":"0"})

    for bc in boundary_electric:
        electric_bcs_dir['boundary_Electric_Dir'].append({"name":bc[0], "value":bc[2]})

    for bc in boundary_Electric_Neu:
        electric_bcs_neu['boundary_Electric_Neu'].append({"name":bc, "value":"0"})

    for bc in boundary_Therm_Neu:
        thermic_bcs_neu['boundary_Therm_Neu'].append({"name":bc, "value":"0"})

    if method_data[3] == "thelec":
        th_ = Merge(thermic_bcs_rob, thermic_bcs_neu)
        if method_data[2] == "Axi":
            return th_
        else:
            elec_ = Merge(electric_bcs_dir, electric_bcs_neu)
            return Merge(th_, elec_)
    elif method_data[3] == 'mag':
        return maxwell_bcs_dir
    elif method_data[3] == 'thmag':
        th_ = Merge(thermic_bcs_rob, thermic_bcs_neu)
        if method_data[2] == "Axi":
            return Merge(maxwell_bcs_dir, th_)
        else:
            elec_ = Merge(electric_bcs_dir, electric_bcs_neu)
            thelec_ = Merge(th_, elec_)
            return Merge(maxwell_bcs_dir, thelec_)
    else:
        th_ = Merge(thermic_bcs_rob, thermic_bcs_neu)
        elec_ = Merge(electric_bcs_dir, electric_bcs_neu)
        thelec_ = Merge(th_, elec_)
        thelecmeca_ = Merge(thelec_, meca_bcs_dir)
        return Merge(maxwell_bcs_dir, thelecmeca_)
            
    pass

def create_json(jsonfile: str, mdict: dict, mmat: dict, mpost: dict, templates: dict, method_data: List[str], debug: bool = False):
    """
    Create a json model file
    """

    print("create_json =", jsonfile)
    data = entry(templates["model"], mdict, debug)

    # material section
    if "Materials" in data:
        for key in mmat:
            data["Materials"][key] = mmat[key]
    else:
        data["Materials"] = mmat
    
    # postprocess
    if method_data[0] == 'cfpdes':
        if method_data[3] != 'mag':
            
            if method_data[0] == "cfpdes":
                section = "heat"
            elif method_data[0] == "CG" or method_data[0] == "HDG":
                section = "temperature"

            if debug: print("flux")
            flux_data = mpost["flux"]
            add = data["PostProcess"][section]["Measures"]["Statistics"]
            odata = entry(templates["flux"], flux_data, debug)
            for md in odata["Flux"]:
                data["PostProcess"][section]["Measures"]["Statistics"][md] = odata["Flux"][md]

            if debug: print("meanT_H")
            meanT_data = mpost["meanT_H"] # { "meanT_H": [] }
            add = data["PostProcess"][section]["Measures"]["Statistics"]
            odata = entry(templates["stats"][0], meanT_data, debug)
            for md in odata["Stats_T"]:
                data["PostProcess"][section]["Measures"]["Statistics"][md] = odata["Stats_T"][md]

        if debug: print("power_H")
        section = "electric"
        if method_data[0] == "cfpdes" and method_data[2] == "Axi" and method_data[3] == 'thelec': section = "heat" 
        elif method_data[0] == "cfpdes" and method_data[2] == "Axi" and method_data[3] != 'thelec': section = "magnetic"
        # elif method_data[0] == "CG" or method_data[0] == "HDG" : section = "magnetic"
        powerH_data = mpost["power_H"] # { "Power_H": [] }
        add = data["PostProcess"][section]["Measures"]["Statistics"]
        if method_data[3] != 'mag':
            odata = entry(templates["stats"][1], powerH_data, debug)
            for md in odata["Stats_Power"]:
                data["PostProcess"][section]["Measures"]["Statistics"][md] = odata["Stats_Power"][md]
    
    mdata = json.dumps(data, indent = 4)

    # print("corrected data:", re.sub(r'},\n					    	}\n', '}\n}\n', data))
    # data = re.sub(r'},\n					    	}\n', '}\n}\n', data)
    with open(jsonfile, "x") as out:
        out.write(mdata)
    pass

def entry_cfg(template: str, rdata: dict, debug: bool = False):
    import chevron

    if debug:
        print("entry/loading %s" % str(template), type(template))
        print("entry/rdata:", rdata)
    with open(template, "r") as f:
        jsonfile = chevron.render(f, rdata)
    jsonfile = jsonfile.replace("\'", "\"")
    return jsonfile

def entry(template: str, rdata: dict, debug: bool = False):
    import chevron
    import re
    
    if debug:
        print("entry/loading %s" % str(template), type(template))
        print("entry/rdata:", rdata)
    with open(template, "r") as f:
        jsonfile = chevron.render(f, rdata)
    jsonfile = jsonfile.replace("\'", "\"")
    
    if debug:
        print("entry/jsonfile:", jsonfile)
        print("corrected:", re.sub(r',(?=\s*\})', '', jsonfile))

    corrected = re.sub(r',(?=\s*\})', '', jsonfile)
    mdata = json.loads(corrected)
    if debug:
        print("entry/data (json):\n", mdata)
   
    return mdata
    
def main():
    """
    """
    print("setup/main")
    import argparse

    # Manage Options
    command_line = None
    parser = argparse.ArgumentParser(description="Create template json model files for Feelpp/HiFiMagnet simu")
    parser.add_argument("--datafile", help="input data file (ex. HL-34-data.json)", default=None)
    parser.add_argument("--wd", help="set a working directory", type=str, default="")
    parser.add_argument("--magnet", help="Magnet name from magnetdb (ex. HL-34)", default=None)

    parser.add_argument("--method", help="choose method (default is cfpdes", type=str,
                    choices=['cfpdes', 'CG', 'HDG', 'CRB'], default='cfpdes')
    parser.add_argument("--time", help="choose time type", type=str,
                    choices=['static', 'transient'], default='static')
    parser.add_argument("--geom", help="choose geom type", type=str,
                    choices=['Axi', '3D'], default='Axi')
    parser.add_argument("--model", help="choose model type", type=str,
                    choices=['thelec', 'mag', 'thmag', 'thmagel'], default='thmagel')
    parser.add_argument("--nonlinear", help="force non-linear", action='store_true')
    parser.add_argument("--cooling", help="choose cooling type", type=str,
                    choices=['mean', 'grad'], default='mean')
    parser.add_argument("--distance_unit", help="distance's unit", type=str,
                    choices=['meter','millimeter'], default='meter')

    parser.add_argument("--debug", help="activate debug", action='store_true')
    parser.add_argument("--verbose", help="activate verbose", action='store_true')
    args = parser.parse_args()

    if args.debug:
        print(args)
    
    # TODO make datafile/magnet exclusive one or the other
    
    # load appenv
    MyEnv = appenv()
    if args.debug: print(MyEnv.template_path())

    # loadconfig
    AppCfg = loadconfig()

    # Get current dir
    cwd = os.getcwd()
    if args.wd:
        os.chdir(args.wd)
    
    # load appropriate templates
    method_data = [args.method, args.time, args.geom, args.model, args.cooling]
    templates = loadtemplates(MyEnv, AppCfg, method_data, (not args.nonlinear) )

    # Get Object
    if args.datafile != None:
        confdata = load_object(MyEnv, args.datafile, args.debug)
        jsonfile = args.datafile.replace(".json","")

    if args.magnet != None:
        confdata = load_object_from_db(MyEnv, "magnet", args.magnet, args.debug)
        jsonfile = args.magnet
    
    # load geom: yamlfile = confdata["geom"]
    part_thermic = []
    part_electric = []
    index_electric = []
    index_Helices = []
    index_Insulators = []

    boundary_meca = []
    boundary_maxwell = []
    boundary_electric = []
    boundary_Therm_Neu = []
    boundary_Electric_Neu = []

    yamlfile = confdata["geom"]
    with open(yamlfile, 'r') as cfgdata:
        cad = yaml.load(cfgdata, Loader = yaml.FullLoader)
        if isinstance(cad, Insert):
            gdata = python_magnetgeo.get_main_characteristics(cad)
            (NHelices, NRings, NChannels, Nsections, R1, R2, Z1, Z2, Zmin, Zmax, Dh, Sh) = gdata
            mu0 = 4*math.pi*1e-7                                                                    # TODO : better manage of mu0
            h = 58222.1                                                                             # TODO : better manage of h

            print("Insert: %s" % cad.name, "NHelices=%d NRings=%d NChannels=%d" % (NHelices, NRings, NChannels))

            for i in range(NHelices):
                part_electric.append("H{}_Cu".format(i+1))
                if args.geom == "Axi":
                    for j in range(Nsections[i]+2):
                        part_thermic.append("H{}_Cu{}".format(i+1,j))
                    for j in range(Nsections[i]):
                        index_electric.append( [str(i+1),str(j+1)] )
                    index_Helices.append(["0:{}".format(Nsections[i]+2)])

                else:
                    part_thermic.append("H{}_Cu".format(i+1))
                    with open(cad.Helices[i]+".yaml", "r") as f:
                        hhelix = yaml.load(f, Loader = yaml.FullLoader)
                        (insulator_name, insulator_number) = hhelix.insulators()
                        #index_Insulators.append((insulator_name, insulator_number))        <--- !! WARNING !! Ignore the insulator for 3D geometry
                
                boundary_Therm_Neu.append("H{}_Interface0".format(i+1))
                boundary_Therm_Neu.append("H{}_Interface1".format(i+1))

                boundary_Electric_Neu.append("H{}_Interface0".format(i+1))
                boundary_Electric_Neu.append("H{}_Interface1".format(i+1))

            for i in range(1,NRings+1):
                part_thermic.append("R{}".format(i))
                part_electric.append("R{}".format(i))

                if i % 2 == 1 :
                    boundary_meca.append("R{}_BP".format(i))
                    boundary_Therm_Neu.append("R{}_BP".format(i))
                    boundary_Electric_Neu.append("R{}_BP".format(i))
                else :
                    boundary_meca.append("R{}_HP".format(i))
                    boundary_Therm_Neu.append("R{}_HP".format(i))
                    boundary_Electric_Neu.append("R{}_HP".format(i))

            for i in range(NChannels):
                boundary_Electric_Neu.append("Channel{}".format(i))

            # Add currentLeads
            if  args.geom == "3D" and len(cad.CurrentLeads):
                part_thermic.append("iL1")
                part_thermic.append("oL2")
                part_electric.append("iL1")
                part_electric.append("oL2")
                boundary_electric.append(["Inner1_LV0", "iL1", "0"])
                boundary_electric.append(["OuterL2_LV0", "oL2", "V0:V0"])
                
                boundary_meca.append("Inner1_LV0")
                boundary_meca.append("OuterL2_LV0")

                boundary_maxwell.append("InfV00")
                boundary_maxwell.append("InfV01")

                boundary_Therm_Neu.append("Inner1_R0n")
                boundary_Therm_Neu.append("Inner1_R1n")
                boundary_Therm_Neu.append("Inner1_LV0")
                boundary_Therm_Neu.append("Inner1_FixingHoles")
                boundary_Therm_Neu.append("OuterL2_R0n")
                boundary_Therm_Neu.append("OuterL2_R1n")
                boundary_Therm_Neu.append("OuterL2_LV0")
                boundary_Therm_Neu.append("OuterL2_CooledSurfaces")
                boundary_Therm_Neu.append("OuterL2_Others")

                boundary_Electric_Neu.append("Inner1_R0n")
                boundary_Electric_Neu.append("Inner1_R1n")
                boundary_Electric_Neu.append("Inner1_FixingHoles")
                boundary_Electric_Neu.append("OuterL2_R0n")
                boundary_Electric_Neu.append("OuterL2_R1n")
                boundary_Electric_Neu.append("OuterL2_CooledSurfaces")
                boundary_Electric_Neu.append("OuterL2_Others")

            else:
                boundary_electric.append(["H1_V0", "H1", "0"])
                boundary_electric.append(["H%d_V0" % NHelices, "H%d" % NHelices, "V0:V0"])
                
                boundary_meca.append("H1_HP")
                boundary_meca.append("H_HP")    
                
            boundary_maxwell.append("InfV1")
            boundary_maxwell.append("InfR1")

            # TODO : manage the scale
            #for i in range(NChannels):
            #     Zmin[i] *= args.scale
            #     Zmax[i] *= args.scale
            #     Dh[i] *= args.scale
            #     Sh[i] *= args.scale

            confdata, gdata, h, mu0 = convert_data(args.distance_unit, confdata, gdata, h, mu0)

            if args.debug:
                print("part_electric:", part_electric)
                print("part_thermic:", part_thermic)

            # params section
            params_data = create_params(gdata, h, mu0, method_data, args.debug)
            
            # bcs section
            bcs_data = create_bcs(args,
                                  boundary_meca, 
                                  boundary_maxwell,
                                  boundary_electric,
                                  boundary_Therm_Neu,
                                  boundary_Electric_Neu,
                                  gdata, confdata, templates, method_data, args.debug) # merge all bcs dict

            # build dict from geom for templates
            # TODO fix initfile name (see create_cfg for the name of output / see directory entry)
            # eg: $home/feelppdb/$directory/cfppdes-heat.save

            main_data = {
                "part_thermic": part_thermic,
                "part_electric": part_electric,
                "index_electric": index_electric,
                "index_V0": boundary_electric,
                "temperature_initfile": "tini.h5",
                "V_initfile": "Vini.h5"
            }
            mdict = Merge( Merge(main_data, params_data), bcs_data)
        
            powerH_data = { "Power_H": [] }
            meanT_data = { "meanT_H": [] }
            if args.geom == "Axi":
                for i in range(NHelices) :
                    powerH_data["Power_H"].append( {"header": "Power_H{}".format(i+1), "name": "H{}_Cu%1%".format(i+1), "index": index_Helices[i]} )
                    meanT_data["meanT_H"].append( {"header": "MeanT_H{}".format(i+1), "name": "H{}_Cu%1%".format(i+1), "index": index_Helices[i]} )
            else:
                for i in range(NHelices) :
                    powerH_data["Power_H"].append( {"header": "Power_H{}".format(i+1), "name": "H{}_Cu".format(i+1)} )
                    meanT_data["meanT_H"].append( {"header": "MeanT_H{}".format(i+1), "name": "H{}_Cu".format(i+1)} )
                # TODO add Glue/Kaptons
                for i in range(NRings) :
                    powerH_data["Power_H"].append( {"header": "Power_R{}".format(i+1), "name": "R{}".format(i+1)} )
                    meanT_data["meanT_H"].append( {"header": "MeanT_R{}".format(i+1), "name": "R{}".format(i+1)} )

                if len(cad.CurrentLeads):
                    powerH_data["Power_H"].append( {"header": "Power_iL1", "name": "iL1"} )
                    powerH_data["Power_H"].append( {"header": "Power_oL2", "name": "oL2"} )
                    meanT_data["meanT_H"].append( {"header": "MeanT_iL1", "name": "iL1"} )
                    meanT_data["meanT_H"].append( {"header": "MeanT_oL2", "name": "oL2"} )

            mpost = { 
                "flux": {'index_h': "0:%s" % str(NChannels)},
                "meanT_H": meanT_data ,
                "power_H": powerH_data 
            }
            mmat = create_materials(gdata, index_Insulators, confdata, templates, method_data, args.debug)

            # create cfg
            if args.datafile: 
                jsonfile = args.datafile.replace("-data.json","")
            if args.magnet: 
                jsonfile = args.magnet
            jsonfile += "-" + args.method
            jsonfile += "-" + args.model
            if args.nonlinear:
                jsonfile += "-nonlinear"
            jsonfile += "-" + args.geom
            jsonfile += "-sim.json"
            cfgfile = jsonfile.replace(".json", ".cfg")

            name = yamlfile.replace(".yaml","")
            create_cfg(cfgfile, name, args.nonlinear, jsonfile, templates["cfg"], method_data, args.debug)
            
            # create json
            create_json(jsonfile, mdict, mmat, mpost, templates, method_data, args.debug)

            # copy some additional json file 
            material_generic_def = ["conductor", "insulator"]

            if args.time == "transient":
                material_generic_def.append("conductor-nosource") # only for transient with mqs

            if args.method == "cfpdes":
                if args.debug: print("cwd=", cwd)
                from shutil import copyfile
                for jsonfile in material_generic_def:
                    filename = AppCfg[args.method][args.time][args.geom][args.model]["filename"][jsonfile]
                    src = os.path.join(MyEnv.template_path(), args.method, args.geom, args.model, filename)
                    dst = os.path.join(jsonfile + "-" + args.method + "-" + args.model + "-" + args.geom + ".json")
                    if args.debug:
                        print(jsonfile, "filename=", filename, "src=%s" % src, "dst=%s" % dst)
                    copyfile(src, dst)
     
        else:
            raise Exception("expected Insert yaml file")

    # Print command to run
    print("\n\n=== Commands to run (ex pour cfpdes/Axi) ===")
    salome = "/home/singularity/hifimagnet-salome-9.7.0.sif"
    feelpp = "/home/singularity/feelpp-toolboxes-v0.109.0.sif"
    partitioner = 'feelpp_mesh_partitioner'
    exec = 'feelpp_toolbox_coefficientformpdes'
    pyfeel = 'cfpdes_insert_fixcurrent.py'
    if args.geom == "Axi" and args.method == "cfpdes" :
        xaofile = cad.name + "-Axi_withAir.xao"
        geocmd = "salome -w1 -t $HIFIMAGNET/HIFIMAGNET_Cmd.py args:%s,--axi,--air,2,2,--wd,$PWD" % (yamlfile)
        
        # if gmsh:
        meshcmd = "python3 -m python_magnetgeo.xao %s --wd $PWD mesh --group CoolingChannels --geo %s --lc=1" % (xaofile, yamlfile)
        meshfile = xaofile.replace(".xao", ".msh")

        # if MeshGems:
        #meshcmd = "salome -w1 -t $HIFIMAGNET/HIFIMAGNET_Cmd.py args:%s,--axi,--air,2,2,mesh,--group,CoolingChannels" % yamlfile
        #meshfile = xaofile.replace(".xao", ".med")
        
        h5file = xaofile.replace(".xao", "_p.json")
        partcmd = "feelpp_mesh_partition --ifile %s --ofile %s [--part NP] [--mesh.scale=0.001]" % (meshfile, h5file)
        feelcmd = "[mpirun -np NP] %s --config-file %s" % (exec, cfgfile)
        pyfeelcmd = "[mpirun -np NP] python %s" % pyfeel
    
        print("Guidelines for running a simu")
        print("export HIFIMAGNET=/opt/SALOME-9.7.0-UB20.04/INSTALL/HIFIMAGNET/bin/salome")
        print("workingdir:", args.wd)
        print("CAD:", "singularity exec %s %s" % (salome,geocmd) )
        # if gmsh
        print("Mesh:", meshcmd)
        # print("Mesh:", "singularity exec -B /opt/DISTENE:/opt/DISTENE:ro %s %s" % (salome,meshcmd))
        print("Partition:", "singularity exec %s %s" % (feelpp, partcmd) )
        print("Feel:", "singularity exec %s %s" % (feelpp, feelcmd) )
        print("pyfeel:", "singularity exec %s %s" % (feelpp, pyfeel))
    pass

if __name__ == "__main__":
    main()
