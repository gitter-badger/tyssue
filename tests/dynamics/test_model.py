import os
import numpy as np

from numpy.testing import assert_almost_equal
from copy import deepcopy

from tyssue.core.sheet import Sheet
from tyssue.geometry.sheet_geometry import SheetGeometry as geom
from tyssue.dynamics.sheet_vertex_model import SheetModel as model
from tyssue import config
from tyssue.stores import stores_dir
from tyssue.dynamics.sheet_isotropic_model import isotropic_relax
from tyssue.io.hdf5 import load_datasets


TOL = 1e-5
DECIMAL = 5


def test_adim():

    default_mod_specs = {
        "face": {
            "contractility": 0.12,
            "vol_elasticity": 1.,
            "prefered_height": 10.,
            "prefered_area": 24.,
            "prefered_vol": 240.,
            },
        "edge": {
            "line_tension": 0.04,
            },
        "vert": {
            "radial_tension": 0.,
            },
        "settings": {
            "grad_norm_factor": 1.,
            "nrj_norm_factor": 1.,
            }
        }
    new_mod_specs = deepcopy(default_mod_specs)
    dim_mod_specs = model.dimensionalize(new_mod_specs)
    new_mod_specs['edge']['line_tension'] = 0.
    assert new_mod_specs['edge']['line_tension'] == 0.
    assert default_mod_specs['edge']['line_tension'] == 0.04
    assert dim_mod_specs['edge']['line_tension'] == 0.04 * 1 * (24*10)**(5/3)


def test_compute_energy():
    h5store = os.path.join(stores_dir, 'small_hexagonal.hf5')
    datasets = load_datasets(h5store,
                             data_names=['face', 'vert', 'edge'])
    specs = config.geometry.cylindrical_sheet()

    sheet = Sheet('emin', datasets, specs)
    nondim_specs = config.dynamics.quasistatic_sheet_spec()
    dim_model_specs = model.dimensionalize(nondim_specs)
    sheet.update_specs(dim_model_specs, reset=True)

    geom.update_all(sheet)
    isotropic_relax(sheet, nondim_specs)

    Et, Ec, Ev = model.compute_energy(sheet, full_output=True)
    assert_almost_equal(Et.mean(), 0.026126171269835349, decimal=DECIMAL)
    assert_almost_equal(Ec.mean(), 0.097547859436179621, decimal=DECIMAL)
    assert_almost_equal(Ev.mean(), 0.11478185003186218, decimal=DECIMAL)

    energy = model.compute_energy(sheet, full_output=False)
    assert_almost_equal(energy, 18.996782315605557, decimal=DECIMAL)


def test_compute_gradient():
    h5store = os.path.join(stores_dir, 'small_hexagonal.hf5')
    datasets = load_datasets(h5store,
                             data_names=['face', 'vert', 'edge'])
    specs = config.geometry.cylindrical_sheet()

    sheet = Sheet('emin', datasets, specs)
    nondim_specs = config.dynamics.quasistatic_sheet_spec()
    dim_model_specs = model.dimensionalize(nondim_specs)
    sheet.update_specs(dim_model_specs)

    geom.update_all(sheet)
    isotropic_relax(sheet, nondim_specs)

    nrj_norm_factor = sheet.specs['settings']['nrj_norm_factor']
    print('Norm factor: ', nrj_norm_factor)
    ((grad_t, _), (grad_c, _),
     (grad_v_srce, grad_v_trgt)) = model.compute_gradient(sheet,
                                                          components=True)
    grad_t_norm = np.linalg.norm(grad_t, axis=0).sum() / nrj_norm_factor
    assert_almost_equal(grad_t_norm, 0.22486850242320636, decimal=DECIMAL)

    grad_c_norm = np.linalg.norm(grad_c, axis=0).sum() / nrj_norm_factor
    assert_almost_equal(grad_c_norm, 0.49692791, decimal=DECIMAL)

    grad_vs_norm = np.linalg.norm(grad_v_srce.dropna(),
                                  axis=0).sum() / nrj_norm_factor
    assert_almost_equal(grad_vs_norm, 0.37818943702074725, decimal=DECIMAL)

    grad_vt_norm = np.linalg.norm(grad_v_trgt.dropna(),
                                  axis=0).sum() / nrj_norm_factor
    assert_almost_equal(grad_vt_norm, 0.32234408741502257, decimal=DECIMAL)