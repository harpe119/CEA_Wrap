import importlib.resources, os, shutil
import appdirs
from zlib import crc32

class Output(dict): # This is just a dictionary that you can also use dot notation to access
  def __init__(self): # Explicitly must receive no arguments, because I don't want to deal with constructor properties
    super().__init__()
    
  def __getattr__(self, name):
    return self[name]
  def __setattr__(self, name, value):
    if name.startswith("_"):
      super().__setattr__(name, value)
    else:
      self[name] = value

def _mutually_exclusive(*args):
  join_set = set()
  for arg in args:
    # First if this contains any elements that were in previous
    if not join_set.isdisjoint(arg):
      return False
    # Then update the current list of existing keys
    join_set.update(arg)
  return True # If none are combined, pass
  
class DataCollector(Output):
  def __init__(self, *args, keys=[], chamber_keys=[], throat_keys=[], exit_keys=[]):
    if len(args) > 0:
      if keys:
        raise TypeError("Data_Collector should not receive both a list of arguments and the 'keys' keyword")
      keys = list(args)
    self._add_element = list.append
    self._keys = keys
    self._chamber_keys = chamber_keys
    self._throat_keys = throat_keys
    self._exit_keys = exit_keys
    
    if not _mutually_exclusive(chamber_keys, throat_keys, exit_keys):
      raise ValueError("Can't have product keys in multiple keys arrays")
      
    if not all([isinstance(val, str) for val in keys + chamber_keys + throat_keys + exit_keys]):
      raise ValueError("All Data_Collector keys must be strings")
      
    for key in keys + chamber_keys + throat_keys + exit_keys:
      self[key] = list()
  
  def add_data(self, data):
    def try_add(key, inner):
      try:
        self[key].append(data[inner][key])
      except KeyError:
        self[key].append(0)
  
    for key in self._keys:
      self[key].append(data[key])
    for key in self._chamber_keys: # First go through chamber products
      try_add(key, "prod_c")
    for key in self._throat_keys: # Then go through throat products
      try_add(key, "prod_t")
    for key in self._exit_keys: # Then go through exit products
      try_add(key, "prod_e")

try:
  import numpy as np
  class NumpyDataCollector(DataCollector):
    def __init__(self, shape, *args, **kwargs):
      if not isinstance(shape, (list, tuple)):
        raise ValueError("shape parameter to NumpyDataCollector must be tuple of output shape")
      self._shape = shape
      
      super().__init__(*args, **kwargs)
      
      # Then we replace all the empty lists with zero-initialized arrays
      for key in self:
        self[key] = np.zeros(shape)
        
    def add_data(self, index, data):
      # index must be either the index for a 1-D array or a tuple for multi-dimensional arrays
      def try_add(key, inner):
        try:
          self[key][index] = data[inner][key]
        except KeyError:
          self[key][index] = 0
    
      for key in self._keys:
        self[key][index] = data[key]
      for key in self._chamber_keys: # First go through chamber products
        try_add(key, "prod_c")
      for key in self._throat_keys: # Then go through throat products
        try_add(key, "prod_t")
      for key in self._exit_keys: # Then go through exit products
        try_add(key, "prod_e")
except ImportError:
  import warnings
  warnings.warn("Numpy is not installed, 'NumpyDataCollector' module will not be available")

def _get_asset(file):
  # The reason the manager is used is because our package may be zipped and the manager extracts it
  #   However, this package is not zip-safe so we just return the location
  with importlib.resources.path(__package__+".assets", file) as manager:
    return str(manager)
    
def _get_data_file(file):
  # Returns a file location in our data directory
  return os.path.join(appdirs.user_data_dir(__package__, False), file)

def cleanup_package_install():
  """
  Cleans up directory structure after install.
  Expected process:
  1st run: There is no AppData folder, all assets are in site-packages\CEA_Wrap\assets folder
           We create AppData\Local\CEA_Wrap and move all our assets there.
           We delete site-packages\CEA_Wrap\assets
  Subsequent runs: We check that the site-packages\CEA_Wrap\assets folder exists and it doesn't so we don't change anything
  Subsequent installs (with --update): The assets folder exists, so we move all assets without replacement, so user thermo_spg.inp files are saved, but any missing assets are added
  """
  try:
    asset_dir = _get_asset("")
  except ModuleNotFoundError: # Raises this if directory doesn't exist
    return False
  data_dir = _get_data_file("")
  if os.path.isdir(asset_dir):
    if not os.path.isdir(data_dir): # Create our destination directory if it doesn't exist
      os.makedirs(data_dir)
    for file in os.listdir(asset_dir):
      if file == "__pycache__": # Evidently the assets thing creates a pycache when it looks for paths
        continue
      src_path = os.path.join(asset_dir, file)
      dst_path = os.path.join(data_dir, file)
      if not os.path.exists(dst_path): # If we don't already have a copy of this file
        shutil.copy2(src_path, dst_path) # Copy it
      os.remove(src_path) # Regardless, remove the assets copy
    shutil.rmtree(asset_dir) # Remove the assets directory when done
  else:
    return False # Nothing was changed because folder doesn't exist

def move_file_if_changed(file, pack_file):
  # file is the local destination, pack_file is the master location
  if os.path.isfile(file):
    # If the file is here, we check the hash of it against the package one
    with open(pack_file, "rb") as f1, open(file, "rb") as f2:
      pack_hash = crc32(f1.read())
      local_hash = crc32(f2.read())
    if pack_hash != local_hash: 
      print(file+" hash does not match package file hash! Updating local file with one from package")
      shutil.copyfile(pack_file, file)
  else:
    # If not here, copy it from package
    print(file+" not found in current directory. Copying from package to current directory...")
    shutil.copyfile(pack_file, file)

def open_thermo_lib():
  """
    Opens the attached thermo library input file using the user's default .inp file viewer (should prompt if none)
  """
  print("Opening user manuals using default .inp file viewer")
  os.system(_get_data_file("thermo_spg.inp"))

def open_pdfs():
  """
    Opens the attached NASA pdfs using the user's default pdf viewer
  """
  print("Opening user manuals using default pdf viewer")
  os.system('"'+_get_data_file("CEA_Mathematical_Analysis.pdf")+'"')
  os.system('"'+_get_data_file("CEA_Users_Manual_and_Program_Description.pdf")+'"')
  
def print_assets_directory():
  """
    Just prints the directory where resources are
  """
  var = os.path.dirname(_get_data_file("FCEA2.exe"))
  print(var)
  return var