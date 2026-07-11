from app.crud.base import CRUDBase
from app.models import Pasaporte
from app.schemas import PasaporteBase, PasaporteUpdate


class CRUDPasaporte(CRUDBase[Pasaporte, PasaporteBase, PasaporteUpdate]):
    """Repositores CRUD con lógica específica para trámites de Pasaportes."""
    pass


crud_pasaporte = CRUDPasaporte(Pasaporte)
