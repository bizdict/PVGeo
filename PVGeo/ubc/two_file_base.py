__all__ = [
    'ubcMeshReaderBase',
    'ModelAppenderBase',
]

__displayname__ = 'Base Classes'

# Outside Imports:
import numpy as np
import pandas as pd
import vtk

from .. import _helpers, base

###############################################################################


# UBC Mesh Reader Base
class ubcMeshReaderBase(base.TwoFileReaderBase):
    """A base class for the UBC mesh readers
    """
    __displayname__ = 'UBC Mesh Reader Base'
    __category__ = 'base'
    extensions = 'mesh msh dat txt text'
    def __init__(self, nOutputPorts=1, outputType='vtkUnstructuredGrid', **kwargs):
        base.TwoFileReaderBase.__init__(self,
            nOutputPorts=nOutputPorts, outputType=outputType,
            **kwargs)
        self.__dataname = 'Data'
        self.__useExtName = True # flag on whether or not to use the model file
                                 # extension as data name
        # For keeping track of type (2D vs 3D)
        self.__sizeM = None


    def Is3D(self):
        return self.__sizeM.shape[0] >= 3

    def Is2D(self):
        return self.__sizeM.shape[0] == 1

    @staticmethod
    def _ubcMesh2D_part(FileName):
        # This is a helper method to read file contents of mesh
        try:
            fileLines = np.genfromtxt(FileName, dtype=str, delimiter='\n', comments='!')
        except (IOError, OSError) as fe:
            raise _helpers.PVGeoError(str(fe))

        def _genTup(sft, n):
            # This reads in the data for a dimension
            pts = []
            disc = []
            for i in range(n):
                ln = fileLines[i+sft].split('!')[0].split()
                if i is 0:
                    o = ln[0]
                    pts.append(o)
                    ln = [ln[1],ln[2]]
                pts.append(ln[0])
                disc.append(ln[1])
            return pts, disc

        # Get the number of lines for each dimension
        nx = int(fileLines[0].split('!')[0])
        nz = int(fileLines[nx+1].split('!')[0])

        # Get the origins and tups for both dimensions
        xpts, xdisc = _genTup(1, nx)
        zpts, zdisc = _genTup(2+nx, nz)

        return xpts, xdisc, zpts, zdisc

    def _ReadExtent(self):
        """Reads the mesh file for the UBC 2D/3D Mesh or OcTree format to get
        output extents. Computationally inexpensive method to discover whole
        output extent.

        Return:
            tuple(int) :
                This returns a tuple of the whole extent for the grid to be
                made of the input mesh file (0,n1-1, 0,n2-1, 0,n3-1). This
                output should be directly passed to set the whole output extent.

        """
        # Read the mesh file as line strings, remove lines with comment = !
        v = np.array(np.__version__.split('.')[0:2], dtype=int)
        FileName = self.GetMeshFileName()
        try:
            if v[0] >= 1 and v[1] >= 10:
                # max_rows in numpy versions >= 1.10
                msh = np.genfromtxt(FileName, delimiter='\n', dtype=np.str,comments='!', max_rows=1)
            else:
                # This reads whole file :(
                msh = np.genfromtxt(FileName, delimiter='\n', dtype=np.str, comments='!')[0]
        except (IOError, OSError) as fe:
            raise _helpers.PVGeoError(str(fe))
        # Fist line is the size of the model
        self.__sizeM = np.array(msh.ravel()[0].split(), dtype=int)
        # Check if the mesh is a UBC 2D mesh
        if self.__sizeM.shape[0] == 1:
            # Read in data from file
            xpts, xdisc, zpts, zdisc = ubcMeshReaderBase._ubcMesh2D_part(FileName)
            nx = np.sum(np.array(xdisc,dtype=int))+1
            nz = np.sum(np.array(zdisc,dtype=int))+1
            return (0,nx, 0,1, 0,nz)
        # Check if the mesh is a UBC 3D mesh or OcTree
        elif self.__sizeM.shape[0] >= 3:
            # Get mesh dimensions
            dim = self.__sizeM[0:3]
            ne,nn,nz = dim[0], dim[1], dim[2]
            return (0,ne, 0,nn, 0,nz)
        else:
            raise _helpers.PVGeoError('File format not recognized')


    @staticmethod
    def ubcModel3D(FileName):
        """Reads the 3D model file and returns a 1D NumPy float array. Use the
        PlaceModelOnMesh() method to associate with a grid.

        Args:
            FileName (str) : The model file name(s) as an absolute path for the
                input model file in UBC 3D Model Model Format. Also accepts a
                `list` of string file names.

        Return:
            np.array :
                Returns a NumPy float array that holds the model data
                read from the file. Use the ``PlaceModelOnMesh()`` method to
                associate with a grid. If a list of file names is given then it
                will return a dictionary of NumPy float array with keys as the
                basenames of the files.
        """
        # Check if recurssion needed
        if type(FileName) is list:
            out = {}
            for f in FileName:
                out[os.path.basename(f)] = ubcMeshReaderBase.ubcModel3D(f)
            return out
        # Perform IO
        try:
            data = np.genfromtxt(FileName, dtype=np.float, comments='!')
        except (IOError, OSError) as fe:
            raise _helpers.PVGeoError(str(fe))
        return data

    def SetUseExtensionAsName(self, flag):
        if self.__useExtName != flag:
            self.__useExtName = flag
            self.Modified(readAgainMesh=False, readAgainModels=False)

    def SetDataName(self, name):
        if name == '':
            self.__useExtName = True
            self.Modified(readAgainMesh=False, readAgainModels=False)
        elif self.__dataname != name:
            self.__dataname = name
            self.__useExtName = False
            self.Modified(readAgainMesh=False, readAgainModels=False)

    def GetDataName(self):
        if self.__useExtName:
            mname = self.GetModelFileNames(idx=0)
            ext = mname.split('.')[-1]
            return ext
        return self.__dataname




###############################################################################


# UBC Model Appender Base
class ModelAppenderBase(base.AlgorithmBase):
    """A base class for create mesh-model appenders on the UBC Mesh formats
    """
    __displayname__ = 'Model Appender Base'
    __category__ = 'base'
    def __init__(self, inputType='vtkRectilinearGrid', outputType='vtkRectilinearGrid', **kwargs):
        base.AlgorithmBase.__init__(self,
            nInputPorts=1, inputType=inputType,
            nOutputPorts=1, outputType=outputType)
        self._modelFileNames = kwargs.get('modelfiles', [])
        self.__dataname = kwargs.get('dataname', 'Appended Data')
        self.__useExtName = True
        self._models = []
        self.__needToRead = True
        self._is3D = None
        # For the VTK/ParaView pipeline
        self.__dt = kwargs.get('dt', 1.0)
        self.__timesteps = None
        self.__inTimesteps = None

    def __SetInputTimesteps(self):
        ints = _helpers.getInputTimeSteps(self)
        self.__inTimesteps = list(ints) if ints is not None else []
        return self.__inTimesteps

    def NeedToRead(self, flag=None):
        """Ask self if the reader needs to read the files again

        Args:
            flag (bool): if the flag is set then this method will set the read
                status

        Return:
            bool:
                The status of the reader aspect of the filter.
        """
        if flag is not None and isinstance(flag, (bool, int)):
            self.__needToRead = flag
            self.__UpdateTimeSteps()
        return self.__needToRead

    def Modified(self, readAgain=True):
        """Call modified if the files needs to be read again again.
        """
        if readAgain: self.__needToRead = readAgain
        base.AlgorithmBase.Modified(self)

    def __UpdateTimeSteps(self):
        """For internal use only: appropriately sets the timesteps.
        """
        if len(self._modelFileNames) > 0 and len(self._modelFileNames) > len(self.__inTimesteps):
            self.__timesteps = _helpers.updateTimeSteps(self, self._modelFileNames, self.__dt)
        # Just use input's time steps which is set by pipeline
        return 1

    def _ReadUpFront(self):
        raise NotImpelementedError()

    def _PlaceOnMesh(self, output, idx=0):
        raise NotImplementedError()


    def RequestData(self, request, inInfo, outInfo):
        """DO NOT OVERRIDE
        """
        # Get input/output of Proxy
        pdi = self.GetInputData(inInfo, 0, 0)
        output = self.GetOutputData(outInfo, 0)
        output.DeepCopy(pdi) # ShallowCopy if you want changes to propagate upstream
        # Get requested time index
        i = _helpers.getRequestedTime(self, outInfo)
        # Perfrom task:
        if self.__needToRead:
            self._ReadUpFront()
        # Place the model data for given timestep onto the mesh
        if len(self._models) > i:
            self._PlaceOnMesh(output, idx=i)
        return 1

    def RequestInformation(self, request, inInfo, outInfo):
        """DO NOT OVERRIDE
        """
        self.__SetInputTimesteps()
        self.__UpdateTimeSteps()
        pdi = self.GetInputData(inInfo, 0, 0)
        # Determine if 2D or 3D and read
        if isinstance(pdi, vtk.vtkRectilinearGrid) and pdi.GetExtent()[3] == 1:
            self._is3D = False
        else:
            self._is3D = True
        return 1

    #### Setters and Getters ####

    def HasModels(self):
        return len(self._modelFileNames) > 0

    def GetTimestepValues(self):
        """Use this in ParaView decorator to register timesteps.
        """
        if self.__timesteps is None: self.__timesteps = self.__SetInputTimesteps()
        # self.__timesteps should already be of type list
        return self.__timesteps if self.__timesteps is not None else None

    def ClearModels(self):
        """Use to clear data file names.
        """
        self._modelFileNames = []
        self._models = []
        self.Modified(readAgain=True)

    def AddModelFileName(self, fname):
        """Use to set the file names for the reader. Handles singlt string or
        list of strings.
        """
        if fname is None:
            return # do nothing if None is passed by a constructor on accident
        if isinstance(fname, list):
            for f in fname:
                self.AddModelFileName(f)
            self.Modified()
        elif fname not in self._modelFileNames:
            self._modelFileNames.append(fname)
            self.Modified()
        return 1

    def GetModelFileNames(self, idx=None):
        """Returns the list of file names or given and index returns a specified
        timestep's filename.
        """
        if idx is None or not self.HasModels():
            return self._modelFileNames
        return self._modelFileNames[idx]

    def SetUseExtensionAsName(self, flag):
        if self.__useExtName != flag:
            self.__useExtName = flag
            self.Modified(readAgain=False)

    def SetDataName(self, name):
        if name == '':
            self.__useExtName = True
            self.Modified(readAgain=False)
        elif self.__dataname != name:
            self.__dataname = name
            self.__useExtName = False
            self.Modified(readAgain=False)

    def GetDataName(self):
        if self.__useExtName:
            mname = self.GetModelFileNames(idx=0)
            ext = mname.split('.')[-1]
            return ext
        return self.__dataname
