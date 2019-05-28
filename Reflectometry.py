import numpy as np
from scipy.special import erfc

from numpy import matmul
from numpy.linalg import inv

delta_factor = (2.818e-13)*(6.02214076e+23)*1e-14/(2*np.pi) #atomic_ratio, density g/cm^3, (lambda nm)^2
n_sigma_roughness = 4
roughness_division = 20

class Sample(object):

    def __init__(self,substrate = None,layers = list()):
        
        if substrate:
            self.set_substrate(substrate)
        self.layers = layers
        self.vacuum = Vacuum()

    def set_substrate(self,substrate):
        self.substrate = substrate

    def add_layer(self,layer):
        self.layers.append(layer)

    def get_total_thickness(self):

        thickness = 0
        for layer in self.layers:
            thickness += layer.thickness

        return thickness

    def get_interfaces_x(self):

        interfaces_x = np.zeros((len(self.layers)+1,))
        for i, layer in enumerate(reversed(self.layers)):
            interfaces_x[i+1] = interfaces_x[i] + layer.thickness

        return interfaces_x

    def get_layers_thickness(self):

        layer_thickness = np.zeros((len(self.layers),))
        for i, layer in enumerate(reversed(self.layers)):
            layer_thickness[i] = layer.thickness

        return layer_thickness

    def get_layers_x(self):

        interfaces_x = self.get_interfaces_x()
        layers_x = (interfaces_x[:-1] + interfaces_x[1:])/2

        return layers_x

    def get_layers_refraction_index(self,lamb):

        layer_refraction_index = np.zeros((len(self.layers)+2,))
        layer_refraction_index[0] = self.vacuum.get_refraction_index(lamb)
        for i, layer in enumerate(reversed(self.layers)):
            layer_refraction_index[i+1] = layer.get_refraction_index(lamb)
        layer_refraction_index[-1] = self.substrate.get_refraction_index(lamb)

        return layer_refraction_index

    def get_interfaces_roughness(self):
        
        interface_roughness = np.zeros((len(self.layers)+1,))
        for i, layer in enumerate(reversed(self.layers)):
            interface_roughness[i] = layer.roughness
        interface_roughness[-1] = self.substrate.roughness

        return interface_roughness

    def get_layers_kz(self,lamb,thetas):

        layer_refraction_index = self.get_layers_refraction_index(lamb)
        layers_kz = (2*np.pi/lamb) * np.sqrt(layer_refraction_index[:,None]**2 - np.cos(thetas[None,:])**2 + 0j)

        return layers_kz

    def get_interfaces_matrix(self,layers_x,layers_kz):

        R = self.get_interfaces_roughness()
        
        kzp = layers_kz[1:,:] + layers_kz[:-1,:] 
        kzm = layers_kz[1:,:] - layers_kz[:-1,:]
        
        interface_matrix = np.zeros([2,2,layers_x.size,layers_kz.shape[1]],dtype = complex)
        interface_matrix[0,0,:,:] = kzp*np.exp(-1j*kzm*layers_x[:,None])*np.exp(-1/2*(kzm*R[:,None])**2)
        interface_matrix[0,1,:,:] = kzm*np.exp(-1j*kzp*layers_x[:,None])*np.exp(-1/2*(kzp*R[:,None])**2)
        interface_matrix[1,0,:,:] = kzm*np.exp(1j*kzp*layers_x[:,None])*np.exp(-1/2*(kzp*R[:,None])**2)
        interface_matrix[1,1,:,:] = kzp*np.exp(1j*kzm*layers_x[:,None])*np.exp(-1/2*(kzm*R[:,None])**2)

        return interface_matrix

    def get_transfert_matrix(self,layers_kz,interface_matrix):

        transfert_matrix = np.zeros((2,2,layers_kz.shape[1]),dtype = complex)
        for i_theta in range(interface_matrix.shape[3]):
            tmp_transfert_matrix = np.eye(2)
            for iX in range(interface_matrix.shape[2]):
                tmp_transfert_matrix = matmul(interface_matrix[:,:,iX,i_theta],tmp_transfert_matrix)#/layers_kz[iX,i_theta]
            transfert_matrix[:,:,i_theta] = tmp_transfert_matrix

        return transfert_matrix

    def get_reflect_coef(self,lamb,thetas):

        X = self.get_interfaces_x()
        layers_kz = self.get_layers_kz(lamb,thetas)
        
        interface_matrix = self.get_interfaces_matrix(X,layers_kz)
        transfert_matrix = self.get_transfert_matrix(layers_kz, interface_matrix)
        
        reflect_coef = transfert_matrix[1,0,:]/transfert_matrix[1,1,:]

        return reflect_coef

    def get_approx_reflect_coef(self,lamb,thetas):
        X = self.get_interfaces_x()
        DX = np.diff(X)
        layers_kz = self.get_layers_kz(lamb,thetas)
        # penetrationIndex = self.getPenetrationIndex(lamb,thetas)

        reflect_coef = np.zeros(thetas.shape)
        layer_kz_real = np.real(layers_kz)
        for i_theta in range(thetas.size):
            # print(penetrationIndex[i_theta],layer_kz_real[1:penetrationIndex[i_theta],i_theta]**2,DX[:penetrationIndex[i_theta]-1])
            ka = -layer_kz_real[0,i_theta]
            kb = -layer_kz_real[-1,i_theta]
            # if penetrationIndex[i_theta]<layer_kz_real.shape[0]-1:
            #     kb = 0
            # else:
            #     kb = -layer_kz_real[layer_kz_real.shape[0]-1,i_theta]
            
            
            theta = thetas[i_theta]
            # kzlin = layer_kz_real[1:penetrationIndex[i_theta],i_theta]
            # dxlin = DX[:penetrationIndex[i_theta]-1]
            kzlin = -layer_kz_real[1:-1,i_theta]
            dxlin = DX
            d = np.sum(dxlin)
            # print(penetrationIndex[i_theta],layer_kz_real[:,i_theta],kb)
            inte = np.sum(kzlin**2*dxlin)
            # print(penetrationIndex[i_theta],ka,kb,d,inte,kzlin,dxlin)
            reflect_coef[i_theta] = (kb-ka+d*kb*ka-inte)/(kb+ka-d*kb*ka-inte)

        return reflect_coef

class Material(object):
    def __init__(self,atomic_mass,atomic_number,unit_cell_volume):

        self.atomic_mass = atomic_mass
        self.atomic_number = atomic_number
        self.unit_cell_volume = unit_cell_volume

class Layer(object):
    def __init__(self,density,thickness,roughness = 0,atomic_mass = 2,atomic_number = 1):
        self.thickness = thickness # nm
        self.density = density # g/cm^3
        self.roughness = roughness # nm
    
        self.atomic_mass = atomic_mass
        self.atomic_number = atomic_number

        self.atomic_ratio = self.atomic_number/self.atomic_mass # nb proton/atomic mass (u)

    def set_thickness(self,thickness):

        self.thickness = thickness

    def set_density(self,density):

        self.density = density

    def get_atomic_density(self):

        return self.density * 6.02214086e+24/10e+24/self.atomic_mass

    def set_roughness(self,roughness):

        self.roughness = roughness

    def get_refraction_index(self,lamb):

        self.atomic_ratio = self.atomic_number/self.atomic_mass

        return 1 - delta_factor*self.density*self.atomic_ratio*lamb**2

class Substrate(Layer):
    def __init__(self,density,roughness = 0,atomic_mass = 2,atomic_number = 1):
        Layer.__init__(self,density,0,roughness,atomic_mass,atomic_number)

class Vacuum(Layer):
    def __init__(self):
        Layer.__init__(self,0,0,0,1)