import os

from fastapi import FastAPI, Depends, Path, Query, Body
from fastapi.logger import logger
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse
from fastapi.responses import FileResponse
from typing import List
from bson.json_util import dumps, loads
from zipfile import ZipFile
import pathlib
import json
from fuse.models.Objects import Passports, ProviderExampleObject, ExampleMetadata

app = FastAPI()

origins = [
    f"http://{os.getenv('HOSTNAME')}:{os.getenv('HOSTPORT')}",
    f"http://{os.getenv('HOSTNAME')}",
    "http://localhost:{os.getenv('HOSTPORT')}",
    "http://localhost",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



    
@app.get("/service-info", summary="Retrieve information about this service")
async def service_info():
    '''
    Returns information about the DRS service

    Extends the v1.0.0 GA4GH Service Info specification as the standardized format for GA4GH web services to self-describe.

    According to the service-info type registry maintained by the Technical Alignment Sub Committee (TASC), a DRS service MUST have:
    - a type.group value of org.ga4gh
    - a type.artifact value of drs

    e.g.
    ```
    {
      "id": "com.example.drs",
      "description": "Serves data according to DRS specification",
      ...
      "type": {
        "group": "org.ga4gh",
        "artifact": "drs"
      }
    ...
    }
    ```
    See the Service Registry Appendix for more information on how to register a DRS service with a service registry.
    '''
    service_info_path = pathlib.Path(__file__).parent / "service_info.json"
    with open(service_info_path) as f:
        return json.load(f)

    
# READ-ONLY endpoints follow the GA4GH DRS API, modeled below
# https://editor.swagger.io/?url=https://ga4gh.github.io/data-repository-service-schemas/preview/release/drs-1.2.0/openapi.yaml
    
@app.get("/objects/{object_id}", summary="Get info about a DrsObject.")
async def objects(object_id: str = Path(default="", description="DrsObject identifier"),
                  expand: bool = Query(default=False, description="If false and the object_id refers to a bundle, then the ContentsObject array contains only those objects directly contained in the bundle. That is, if the bundle contains other bundles, those other bundles are not recursively included in the result. If true and the object_id refers to a bundle, then the entire set of objects in the bundle is expanded. That is, if the bundle contains aother bundles, then those other bundles are recursively expanded and included in the result. Recursion continues through the entire sub-tree of the bundle. If the object_id refers to a blob, then the query parameter is ignored.")):
    '''
    Returns object metadata, and a list of access methods that can be used to fetch object bytes.
    '''
    example_object = ExampleMetadata()
    example_object.access_methods = [
        {
            "type": "GET",
            "access_url": {
                "url": "http://localhost:8083/files/" + object_id
            },
        }
    ]

    if not object_id == "exampleszip.zip":
        example_object.contents =  [
            {
                "name": object_id,
                "id": object_id,
                "drs_uri": "drs://drs.example.org/314159",
            }
        ]
    else:
        example_object.contents =  [
            {
                "name": "HPA.csv",
                "id": "HPA.csv",
                "drs_uri": "drs://drs.example.org/314159",
            },
            {
                "name": "TestPhenotypes_3.csv",
                "id": "TestPhenotypes_3.csv",
                "drs_uri": "drs://drs.example.org/314159",
            }
        ]

    return example_object.dict()

# @app.get("/files/{file_name}", summary="Get file.")
# async def files(file_name: str = Path(default="", description="File name")):
#     '''
#     Returns file metadata, and a list of access methods that can be used to fetch the file.
#     :param file_name:
#     :return:
#     '''
#     dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")
#     file_path = os.path.join(dir_path, file_name)
#     # return FileResponse(file_path)
#     def iterfile():
#         try:
#             with open(file_path, mode="rb") as file_data:
#                 yield from file_data
#         except:
#             raise Exception()
#
#     response = StreamingResponse(iterfile(), media_type="application/zip")
#     response.headers["Content-Disposition"] = "attachment; filename=examples"
#     return response



# xxx add value for passport example that doesn't cause server error
# xxx figure out how to add the following description to 'passports':
# the encoded JWT GA4GH Passport that contains embedded Visas. The overall JWT is signed as are the individual Passport Visas
@app.post("/objects/{object_id}", summary="Get info about a DrsObject through POST'ing a Passport.")
async def post_objects(object_id: str = Path(default="", description="DrsObject identifier"),
                       expand: bool = Query(default=False, description="If false and the object_id refers to a bundle, then the ContentsObject array contains only those objects directly contained in the bundle. That is, if the bundle contains other bundles, those other bundles are not recursively included in the result. If true and the object_id refers to a bundle, then the entire set of objects in the bundle is expanded. That is, if the bundle contains aother bundles, then those other bundles are recursively expanded and included in the result. Recursion continues through the entire sub-tree of the bundle. If the object_id refers to a blob, then the query parameter is ignored."),
                       passports: Passports = Depends(Passports.as_form)):
    '''
    Returns object metadata, and a list of access methods that can be
    used to fetch object bytes. Method is a POST to accomodate a JWT
    GA4GH Passport sent in the formData in order to authorize access.
    '''
    example_object = ProviderExampleObject()
    return example_object.dict()

@app.get("/objects/{object_id}/access/{access_id}", summary="Get a URL for fetching bytes")
async def get_objects(object_id: str=Path(default="", description="DrsObject identifier"),
                      access_id: str=Path(default="", description="An access_id from the access_methods list of a DrsObject")):
    '''
    Returns a URL that can be used to fetch the bytes of a
    DrsObject. This method only needs to be called when using an
    AccessMethod that contains an access_id (e.g., for servers that
    use signed URLs for fetching object bytes).
    '''


    return {
        "url": "http://localhost:8083/files/" + object_id,
        "headers": "Authorization: None"
    }

@app.get("/files/{object_id}", summary="Get a URL for fetching bytes")
async def get_examples(object_id: str):
    examples_zip_path = pathlib.Path('exampleszip')
    if not examples_zip_path.exists():
        # print("generating zip")
        local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")
        ezip = ZipFile('exampleszip', 'w')
        ezip.write((os.path.join(local_path, f"HPA.csv")), 'HPA.csv')
        ezip.write(os.path.join(local_path, f"TestPhenotypes_3.csv"), 'TestPhenotypes_3.csv')
        # ezip.printdir()
        ezip.close()

    if not (object_id == 'exampleszip.zip'):
        dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")
        local_path = os.path.join(dir_path, object_id)
        file_type = "text/csv"
    else:
        local_path = object_id
        file_type = "application/zip"

    def iterfile():
        try:
            with open(local_path, mode="rb") as file_data:
                yield from file_data
        except:
            raise Exception()



    response = StreamingResponse(iterfile(), media_type=file_type)
    response.headers["Content-Disposition"] = "attachment; filename=examples"
    return response


# xxx figure out how to add the following description to 'passports':
# the encoded JWT GA4GH Passport that contains embedded Visas. The overall JWT is signed as are the individual Passport Visas.
@app.post("/objects/{object_id}/access/{access_id}", summary="Get a URL for fetching bytes through POST'ing a Passport")
async def post_objects(object_id: str=Path(default="", description="DrsObject identifier"),
                       access_id: str=Path(default="", description="An access_id from the access_methods list of a DrsObject"),
                       passports: Passports = Depends(Passports.as_form)):
    '''
    Returns a URL that can be used to fetch the bytes of a
    DrsObject. This method only needs to be called when using an
    AccessMethod that contains an access_id (e.g., for servers that
    use signed URLs for fetching object bytes). Method is a POST to
    accomodate a JWT GA4GH Passport sent in the formData in order to
    authorize access.

    '''
    return {
        "url": "http://localhost/object.zip",
        "headers": "Authorization: None"
    }

