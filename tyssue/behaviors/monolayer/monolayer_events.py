import logging
from ...topology.bulk_topology import IH_transition, HI_transition

# from ..topology.sheet_topology import (remove_face,
#                                        type1_transition,
#                                        cell_division)
logger = logging.getLogger(__name__)


def apoptosis(
    monolayer,
    manager,
    cell_id,
    contract_rate=2.0,
    critical_area=1e-2,
    shrink_rate=0.4,
    critical_volume=0.1,
):
    """Apoptotic behavior

    Parameters
    ----------
    monolayer : a :cass:`Monolayer` object
    manager : a :class:`EventManager` object
    cell_id : int
       id of the apoptotic cell
    contract_rate : float, default 2.
    critical_area : float, default 1e-2,
    shrink_rate : float, default 0.4,
    critical_volume : float, default 0.1,
    """
    # TODO complete docstring
    # TODO setup default / kwargs mechanisms
    settings = {
        "contract_rate": contract_rate,
        "critical_area": critical_area,
        "shrink_rate": shrink_rate,
        "critical_volume": critical_volume,
    }

    cell = cell_id
    if cell is None:
        return
    done = False

    cell_to_face = monolayer.get_orbits("cell", "face")
    try:
        apical_face = monolayer.face_df[
            (monolayer.face_df.index.isin(cell_to_face[cell]))
            & (monolayer.face_df.segment == "apical")
        ].index[0]
    except Exception:  # TODO fix that
        apical_face = None
    # Apical face has already been removed.
    # It needs to eliminate lateral face until obtain a cell with 4 faces.
    if apical_face is None:
        faces_in_cell = monolayer.face_df.loc[cell_to_face[cell].unique()]
        if len(faces_in_cell) > 4:
            # Remove lateral face with 3 sides
            face_to_eliminate = faces_in_cell[
                (faces_in_cell.segment == "lateral") & (faces_in_cell.num_sides == 3)
            ].index[0]

            prev_nums = {
                "edge": monolayer.Ne,
                "face": monolayer.Nf,
                "vert": monolayer.Nv,
            }
            HI_transition(monolayer, face_to_eliminate)
            monolayer.face_df.loc[prev_nums["face"] :, "contractility"] = 0
            done = False
        elif len(faces_in_cell) == 4:
            # Volume reduction
            if monolayer.cell_df.loc[cell, "vol"] > critical_volume:
                shrink(monolayer, cell, shrink_rate)
                done = False
            else:
                done = True
    else:
        # Contract apical surface until reached a critical area
        if monolayer.face_df.loc[apical_face, "area"] > critical_area:
            contract(monolayer, apical_face, contract_rate, True)
            done = False

        elif monolayer.face_df.loc[apical_face, "area"] <= critical_area:
            # Reduce neighbours for the apical face (until 3)
            if monolayer.face_df.loc[apical_face, "num_sides"] > 3:
                e_min = monolayer.edge_df[monolayer.edge_df["face"] == apical_face][
                    "length"
                ].idxmin()
                prev_nums = {
                    "edge": monolayer.Ne,
                    "face": monolayer.Nf,
                    "vert": monolayer.Nv,
                }

                monolayer.settings["threshold_length"] = 1e-3
                IH_transition(monolayer, e_min)
                monolayer.face_df.loc[prev_nums["face"] :, "contractility"] = 0

                done = False

            elif monolayer.face_df.loc[apical_face, "num_sides"] == 3:
                prev_nums = {
                    "edge": monolayer.Ne,
                    "face": monolayer.Nf,
                    "vert": monolayer.Nv,
                }
                HI_transition(monolayer, apical_face)
                done = False

    if not done:
        manager.append(apoptosis, cell_id, kwargs=settings)


def shrink(monolayer, cell, shrink_rate):
    """Divides the equilibrium volume of the cell
    by a factor (1+shrink_rate) and its equilibrium area
    by (1+shrink_rate)^2/3
    """
    factor = 1 + shrink_rate
    monolayer.cell_df.loc[cell, "prefered_vol"] /= factor
    monolayer.cell_df.loc[cell, "prefered_area"] /= factor ** (2 / 3)


def grow(monolayer, cell, grow_rate):
    """Multiplies the equilibrium volume of face
    by a factor (1+shrink_rate)
    """
    factor = 1 + grow_rate
    faces = monolayer.edge_df[monolayer.edge_df["cell"] == cell]["face"]
    monolayer.cell_df.loc[cell, "prefered_vol"] *= factor
    monolayer.face_df.loc[faces, "prefered_area"] *= factor ** (2 / 3)


def ab_pull(monolayer, cell, *args):
    """Adds a linear tension to the apical-to-basal edges
    of a cell
    """
    cell_edges = monolayer.edge_df[monolayer.edge_df["cell"] == cell]
    lateral_edges = cell_edges[cell_edges["segment"] == "lateral"]
    srce_segment = monolayer.upcast_srce(monolayer.vert_df["segment"]).loc[
        lateral_edges.index
    ]
    trgt_segment = monolayer.upcast_trgt(monolayer.vert_df["segment"]).loc[
        lateral_edges.index
    ]

    ab_edges = lateral_edges[
        (srce_segment == "apical") & (trgt_segment == "basal")
    ].index
    ba_edges = lateral_edges[
        (trgt_segment == "apical") & (srce_segment == "basal")
    ].index
    # TODO treat factor directly - not as a multiple of
    # the default line_tension (which might be 0)
    factor = args[0]
    new_tension = monolayer.specs["edge"]["line_tension"] * factor
    monolayer.edge_df.loc[ab_edges, "line_tension"] += new_tension
    monolayer.edge_df.loc[ba_edges, "line_tension"] += new_tension


def contract(monolayer, face, contractile_increase, multiple=False):
    """
    Contract the face by increasing the 'contractility' parameter
    by contractile_increase
    """
    if multiple:
        monolayer.face_df.loc[face, "contractility"] *= contractile_increase
    else:
        monolayer.face_df.loc[face, "contractility"] += contractile_increase


def contract_apical_face(
    monolayer,
    face_id,
    contractile_increase=1.0,
    critical_area=1e-2,
    max_contractility=50,
):
    """Single step contraction event for apical face only
    """
    face = monolayer.idx_lookup(face_id, "face")
    if face is None:
        return
    if (
        (monolayer.face_df.loc[face, "segment"] != "apical")
        or (monolayer.face_df.loc[face, "area"] < critical_area)
        or (monolayer.face_df.loc[face, "contractility"] > max_contractility)
    ):
        return
    contract(monolayer, face, contractile_increase)
