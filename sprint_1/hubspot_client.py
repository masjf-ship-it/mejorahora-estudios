# -*- coding: utf-8 -*-
"""
Cliente minimo para HubSpot CRM v3.
Lee el token desde sprint_1/config.ini [HUBSPOT] token.

Uso:
    from hubspot_client import HubSpotClient
    hs = HubSpotClient.from_config()
    contact = hs.search_contact_by_email("cliente@ejemplo.com")
    owner = hs.get_owner(contact["owner_id"])
"""
import configparser
import os
import time
import urllib.parse
import urllib.request
import urllib.error
import json


BASE_URL = "https://api.hubapi.com"


class HubSpotClient:
    def __init__(self, token: str, portal_id: str = ""):
        if not token or not token.startswith("pat-"):
            raise ValueError("Token HubSpot invalido o vacio")
        self.token = token
        self.portal_id = portal_id

    @classmethod
    def from_config(cls, config_path: str = None) -> "HubSpotClient":
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.ini")
        cfg = configparser.ConfigParser()
        cfg.read(config_path, encoding="utf-8")
        if "HUBSPOT" not in cfg:
            raise RuntimeError("Seccion [HUBSPOT] no existe en " + config_path)
        token = cfg["HUBSPOT"].get("token", "").strip()
        portal_id = cfg["HUBSPOT"].get("portal_id", "").strip()
        return cls(token, portal_id)

    def _request(self, method: str, path: str, body: dict = None, retries: int = 2) -> dict:
        url = BASE_URL + path
        headers = {
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
        }
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        last_exc = None
        for attempt in range(retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    raw = r.read()
                    if not raw:
                        return {}
                    return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as e:
                # 429 o 5xx → backoff
                if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    last_exc = e
                    continue
                raise
            except urllib.error.URLError as e:
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    last_exc = e
                    continue
                raise
        if last_exc:
            raise last_exc
        return {}

    # -------- Owners --------
    def list_owners(self) -> list:
        """Devuelve todos los owners de la cuenta."""
        out = []
        after = None
        while True:
            q = "?limit=100"
            if after:
                q += "&after=" + urllib.parse.quote(str(after))
            resp = self._request("GET", "/crm/v3/owners/" + q)
            out.extend(resp.get("results", []))
            paging = resp.get("paging", {}).get("next")
            if not paging:
                break
            after = paging.get("after")
            if not after:
                break
        return out

    def get_owner(self, owner_id: str) -> dict:
        if not owner_id:
            return {}
        return self._request("GET", "/crm/v3/owners/" + str(owner_id))

    # -------- Contacts --------
    def search_contact_by_email(self, email: str, properties: list = None) -> dict:
        if not email:
            return {}
        props = properties or ["firstname", "lastname", "phone", "hubspot_owner_id"]
        body = {
            "filterGroups": [{
                "filters": [{"propertyName": "email", "operator": "EQ", "value": email}]
            }],
            "properties": props,
            "limit": 1,
        }
        resp = self._request("POST", "/crm/v3/objects/contacts/search", body=body)
        results = resp.get("results", [])
        return results[0] if results else {}

    def search_contact_by_phone(self, phone: str, properties: list = None) -> dict:
        if not phone:
            return {}
        props = properties or ["firstname", "lastname", "email", "hubspot_owner_id"]
        body = {
            "filterGroups": [{
                "filters": [{"propertyName": "phone", "operator": "EQ", "value": phone}]
            }],
            "properties": props,
            "limit": 1,
        }
        resp = self._request("POST", "/crm/v3/objects/contacts/search", body=body)
        results = resp.get("results", [])
        return results[0] if results else {}

    def search_contact_by_cedula(self, cedula: str, properties: list = None) -> dict:
        """Busca por numero de identificacion (varias propiedades candidatas).

        HubSpot guarda la cedula en propiedades con distintos nombres segun como
        se haya configurado el formulario. Se prueban en orden hasta encontrar hit.
        """
        if not cedula:
            return {}
        cedula = str(cedula).strip()
        props = properties or [
            "firstname", "lastname", "email", "phone", "hubspot_owner_id",
            "banco", "banco_donde_tienes_la_hipoteca_o_leasing_habitacional",
        ]
        # Propiedades candidatas donde guardamos el CC en HubSpot (ordenadas)
        cedula_props = [
            "numero_de_identificacion",
            "identificacion",
            "cedula",
            "numero_de_cedula",
            "n_de_identificacion",
        ]
        for prop in cedula_props:
            body = {
                "filterGroups": [{
                    "filters": [{"propertyName": prop, "operator": "EQ", "value": cedula}]
                }],
                "properties": props,
                "limit": 1,
            }
            try:
                resp = self._request("POST", "/crm/v3/objects/contacts/search", body=body)
            except urllib.error.HTTPError as e:
                # Propiedad no existe en el portal -> 400, intentar siguiente
                if e.code == 400:
                    continue
                raise
            results = resp.get("results", [])
            if results:
                return results[0]
        return {}

    def search_contact_by_name(self, nombre: str, properties: list = None) -> dict:
        """Busca contacto por nombre completo con dos estrategias en cascada.

        R-DVV-17C (2026-04-29): Estrategia mejorada para manejar contactos donde
        el nombre completo esta en el campo firstname (sin split firstname/lastname).

        Estrategia A (todos los tokens en firstname):
          Busca que firstname CONTAINS_TOKEN cada token del nombre.
          Captura contactos creados con nombre completo en firstname.
          Ej: firstname="JORGE LUIS VELASCO SALAZAR" → todos los tokens hacen match.
          Evita falsos positivos: "JORGE EMILIO SALAZAR RUIZ" no contiene "VELASCO".

        Estrategia B (primer token en firstname, ultimo en lastname) [fallback]:
          Busca contactos con split correcto firstname/lastname.
          Solo se usa si Estrategia A no devuelve exactamente 1 resultado.

        En ambos casos: solo devuelve resultado si hay exactamente 1 match.
        """
        if not nombre:
            return {}
        tokens = [t for t in nombre.strip().split() if t]
        if not tokens:
            return {}
        props = properties or ["firstname", "lastname", "email", "phone", "hubspot_owner_id"]

        # Estrategia A: todos los tokens en firstname (hasta 5 para no exceder limite HubSpot)
        tokens_a = tokens[:5]
        filters_a = [{"propertyName": "firstname", "operator": "CONTAINS_TOKEN", "value": t}
                     for t in tokens_a]
        body_a = {"filterGroups": [{"filters": filters_a}], "properties": props, "limit": 5}
        try:
            resp_a = self._request("POST", "/crm/v3/objects/contacts/search", body=body_a)
            results_a = resp_a.get("results", [])
            if len(results_a) == 1:
                return results_a[0]
        except Exception:
            pass

        # Estrategia B: primer token en firstname + ultimo token en lastname
        firstname = tokens[0]
        lastname = tokens[-1] if len(tokens) > 1 else ""
        filters_b = [{"propertyName": "firstname", "operator": "CONTAINS_TOKEN", "value": firstname}]
        if lastname:
            filters_b.append({"propertyName": "lastname", "operator": "CONTAINS_TOKEN", "value": lastname})
        body_b = {"filterGroups": [{"filters": filters_b}], "properties": props, "limit": 5}
        resp_b = self._request("POST", "/crm/v3/objects/contacts/search", body=body_b)
        results_b = resp_b.get("results", [])
        if len(results_b) == 1:
            return results_b[0]
        return {}

    def match_contact_cascade(self, cedula: str = "", email: str = "", nombre: str = "",
                               properties: list = None) -> dict:
        """Cascada de matching CC -> email -> nombre. Retorna dict con metadato:
            {
              'contact': <resultado HubSpot o {}>,
              'matched_by': 'cedula' | 'email' | 'nombre' | None,
            }
        """
        if cedula:
            c = self.search_contact_by_cedula(cedula, properties=properties)
            if c:
                return {"contact": c, "matched_by": "cedula"}
        if email:
            c = self.search_contact_by_email(email, properties=properties)
            if c:
                return {"contact": c, "matched_by": "email"}
        if nombre:
            c = self.search_contact_by_name(nombre, properties=properties)
            if c:
                return {"contact": c, "matched_by": "nombre"}
        return {"contact": {}, "matched_by": None}


if __name__ == "__main__":
    # Smoke test: lista los primeros 3 owners
    hs = HubSpotClient.from_config()
    owners = hs.list_owners()
    print("Owners encontrados:", len(owners))
    for o in owners[:3]:
        print(" -", o.get("id"), o.get("firstName"), o.get("lastName"), o.get("email"))
