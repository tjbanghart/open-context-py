import re
import os
import json
import codecs
import requests
from lxml import etree
import lxml.html
from unidecode import unidecode
from django.conf import settings
from django.db import connection
from django.db.models import Q
from django.db.models import Avg, Max, Min
from time import sleep
from django.utils.http import urlquote, quote_plus, urlquote_plus
from opencontext_py.libs.general import LastUpdatedOrderedDict
from opencontext_py.libs.generalapi import GeneralAPI
from opencontext_py.apps.ldata.linkannotations.models import LinkAnnotation as LinkAnnotation
from opencontext_py.apps.ldata.linkentities.models import LinkEntity as LinkEntity
from opencontext_py.apps.ocitems.assertions.models import Assertion
from opencontext_py.apps.ocitems.manifest.models import Manifest as Manifest
from opencontext_py.apps.ocitems.subjects.models import Subject
from opencontext_py.apps.ocitems.mediafiles.models import Mediafile as Mediafile
from opencontext_py.apps.ocitems.persons.models import Person as Person
from opencontext_py.apps.ocitems.projects.models import Project as Project
from opencontext_py.apps.ocitems.documents.models import OCdocument as OCdocument
from opencontext_py.apps.ocitems.strings.models import OCstring as OCstring
from opencontext_py.apps.ocitems.octypes.models import OCtype as OCtype
from opencontext_py.apps.ocitems.predicates.models import Predicate as Predicate
from opencontext_py.apps.ocitems.projects.models import Project as Project
from opencontext_py.apps.ocitems.geospace.models import Geospace
from opencontext_py.apps.ocitems.events.models import Event
from opencontext_py.apps.ocitems.identifiers.models import StableIdentifer
from opencontext_py.apps.ocitems.obsmetadata.models import ObsMetadata
from opencontext_py.apps.edit.items.itembasic import ItemBasicEdit
from opencontext_py.apps.imports.poggiociv.models import PoggioCiv


class PoggioCivLoci():
    """ Class for getting data from the legacy Poggio Civitate server

To do:
- Fix associations between trench books and trenches.
- trench-books-index.json has the links between trench books and trenches.
- What needs to change first is the link between the Tr and the parent trench.
- For example Tr-105 should be in Tesoro 21
- several other trench-book associations are also wrong and need to be
- updated using trench-books-index.json


from opencontext_py.apps.imports.poggiociv.loci import PoggioCivLoci
pcl = PoggioCivLoci()
all_data = pcl.scrape_locus_pages()



    """

    def __init__(self):
        self.act_import_dir = False
        self.source_id = 'tb-scrape'
        self.pc = PoggioCiv() 
        self.pc_directory = 'mag-data'
        self.trench_book_index_json = 'trench-books-index.json'
        self.locus_data_json = 'all-locus-data.json'
        self.locus_data_csv = 'all-locus-data.csv'
        self.project_uuid = 'DF043419-F23B-41DA-7E4D-EE52AF22F92F'
        self.part_of_pred_uuid = '0BB889F9-54DD-4F70-5B63-F5D82425F0DB'
        self.tb_index = None
        self.locus_files = None
        self.field_keys = [
            'file',
            'lid',
            'locus',
            'tbtdid',
            'tbtid',
            'trench book uuid',
            'trend book label',
            'trench uuid',
            'trench label',
            'trench path',
            'unit uuid',
            'unit path',
            'Locus Number',
            'Open Date',
            'Open Date Page',
            'Closing Date',
            'Closing Date Page',
            'Description',
            'Munsell Designation',
            'Opening Grid Coordinates',
            'Closing Grid Coordinates',
            'Soil Samples Taken',
            'Photos Taken'
        ]
        self.fields = {
            'Locus Number': {
                'start_str': '<tr><td width="140"><b>Locus Number:</b></td><td style="padding-left:20px">',
                'end_str': '</td></tr>',
                'sub': None
            },
            'Open Date Page': {
                'start_str': '<tr><td><b>Open Date:</b></td><td style="padding-left:20px">',
                'end_str': '</td></tr>',
                'sub': {
                    'Open Date': {
                        'start_str': '',
                        'end_str': ',',
                    },
                    'Open Date Page': {
                        'start_str': 'p. ',
                        'end_str': '',
                    }
                }
            },
            'Closing Date Page': {
                'start_str': '<tr><td><b>Closing Date:</b></td><td style="padding-left:20px">',
                'end_str': '</td></tr>',
                'sub': {
                    'Closing Date': {
                        'start_str': '',
                        'end_str': ',',
                    },
                    'Closing Date Page': {
                        'start_str': 'p. ',
                        'end_str': '',
                    }
                }
            },
            'Description': {
                'start_str': '<tr><td valign="top"><b>Description:</b></td><td style="padding-left:20px">',
                'end_str': '</td></tr>',
                'sub': None
            },
            'Munsell Designation': {
                'start_str': '<tr><td><b>Munsell Designation:</b></td><td style="padding-left:20px">',
                'end_str': '</td></tr>',
                'sub': None
            },
            'Opening Grid Coordinates A': {
                'start_str': '<tr><td valign="top"><b>Opening Grid Coordinates:</b></td>',
                'end_str': '</table>',
                'sub': {
                    'Opening Grid Coordinates': {
                        'start_str': '<table>',
                        'end_str': '',
                    }
                }
            },
            'Closing Grid Coordinates A': {
                'start_str': '<tr><td valign="top"><b>Closing Grid Coordinates:</b></td>',
                'end_str': '</table>',
                'sub': {
                    'Closing Grid Coordinates': {
                        'start_str': '<table>',
                        'end_str': '',
                    }
                }
            },
            'Soil Samples Taken': {
                'start_str': '<tr><td><b>Soil Samples Taken:</b></td><td style="padding-left:20px">',
                'end_str': '</td></tr>',
                'sub': None
            },
            'Photos Taken': {
                'start_str': '<tr><td><b>Photos Taken:</b></td><td style="padding-left:20px">',
                'end_str': '</td></tr>',
                'sub': None
            }
        }
    
    def scrape_locus_pages(self):
        """ scrape data from locus pages """
        self.load_root_index()
        self.get_locus_files_list()
        if isinstance(self.locus_files, list):
            all_data = []
            for locus_page in self.locus_files:
                data = self.scrape_locus_page(locus_page)
                if data is not None:
                    all_data.append(data)
        self.pc.save_as_json_file(self.pc.pc_directory,
                                  self.locus_data_json,
                                  all_data)
        self.pc.save_as_csv_file(self.pc.pc_directory,
                                self.locus_data_csv,
                                self.field_keys,
                                all_data)
        return all_data
    
    def scrape_locus_page(self, locus_page):
        """ loads and scrapes a locus page """
        data = None
        dir_file = self.pc.define_import_directory_file(self.pc.pc_directory,
                                                        locus_page)
        page_str = self.pc.load_file(dir_file)
        if not isinstance(page_str, str):
            print('failed to open ' + dir_file)
        else:
            data = self.prep_locus_data(locus_page)
            for f_key, field_dict in self.fields.items():
                f_value = self.get_str_between_start_end(page_str,
                                                         field_dict['start_str'],
                                                         field_dict['end_str'])
                if isinstance(f_value, str):
                    if field_dict['sub'] is not None:
                        for sub_f_key, sub_dict in field_dict['sub'].items():
                            sub_f_value = self.get_str_between_start_end(f_value,
                                                                         sub_dict['start_str'],
                                                                         sub_dict['end_str'])
                            if isinstance(sub_f_value, str):
                                if 'Coordinates' in sub_f_key:
                                    sub_f_value = sub_f_value.replace(' style="padding-left:20px"', '')
                                    sub_f_value = '<table class="table table-condensed">' + sub_f_value + '</table>'
                                    sub_f_value = '<div class="table-responsive">' + sub_f_value + '</div>'
                                data[sub_f_key] = sub_f_value
                            else:
                                data[sub_f_key] = None
                    else:
                        # no subvalues 
                        data[f_key] = f_value
                else:
                    data[f_key] = None
            # now add some extra context data for trench books, trenches if present
            data = self.add_trench_book_data(data)
            data = self.add_trench_data(data)
            new_data = LastUpdatedOrderedDict()
            for field_key in self.field_keys:
                new_data[field_key] = data[field_key]
                if data[field_key] is None:
                    new_data[field_key] = ''
            data = new_data
            return data

    def prep_locus_data(self, locus_page):
        """ gets parameters from the locus page """
        data = LastUpdatedOrderedDict()
        for field_key in self.field_keys:
            data[field_key] = None
        data['file'] = locus_page
        locus_page= locus_page.replace('.html', '')
        if '---' in locus_page:
            l_ex_a = locus_page.split('---')
            params_str = l_ex_a[1]
            if '--' in params_str:
                params_vals = params_str.split('--')
            else:
                params_vals = [params_str]
            for param_val in params_vals:
                p_v_ex = param_val.split('-')
                key = p_v_ex[0]
                val = p_v_ex[1]
                data[key] = val
        return data
    
    def add_trench_book_data(self, data):
        """ gets the trench book associated with a current tbtdid """
        tbtdid = data['tbtdid']
        try:
            tbtdid = int(float(tbtdid))
        except:
            tbtdid = None
        if isinstance(self.tb_index, list) and tbtdid is not None:
            for tb_item in self.tb_index:
                if 'tbtdid' in tb_item and 'trench_book_uuid' in tb_item:
                    if tb_item['tbtdid'] == tbtdid:
                        if isinstance(tb_item['trench_book_uuid'], str):
                            tb_man_obj = self.get_man_obj_by_uuid(tb_item['trench_book_uuid'])
                            if tb_man_obj is not None:
                                data['trench book uuid'] = tb_man_obj.uuid
                                data['trend book label'] = tb_man_obj.label
                                break
        return data
    
    def add_trench_data(self, data):
        """ gets the trench book associated with a current tbtid """
        tbtid = data['tbtid']
        closeing = data['Closing Date']
        try:
            tbtid = int(float(tbtid))
        except:
            tbtid = None
        if isinstance(self.tb_index, list) and tbtid is not None and closeing is not None:
            # print('Check: ' + str(tbtid) + ', year: ' + str(closeing) + '.')
            tbtid = int(float(tbtid))
            year = None
            cl_ex = closeing.split('/')
            if len(cl_ex) > 2:
                try:
                    year = int(float(cl_ex[2]))
                except:
                    year = None
            if year is not None:
                 # print('Check: ' + str(tbtid) + ', year: ' + str(year) + '.')
                for tb_item in self.tb_index:
                    if 'tbtid' in tb_item and 'trenches' in tb_item:
                        if tb_item['tbtid'] == tbtid:
                            for trench in tb_item['trenches']:
                                data['trench uuid'] = trench['trench_uuid']
                                data['trench label'] = trench['label']
                                if trench['year'] == year and isinstance(trench['unit_year_uuid'], str):
                                    data['unit uuid'] = trench['unit_year_uuid']
                                    data['unit path'] = self.get_subject_context_by_uuid(trench['unit_year_uuid'])
                                    break
        if isinstance(data['trench label'], str) and data['trench uuid'] is None:
            # we have a trench label, but no UUID. Check database to get UUID
            man_obj = self.get_man_trench_by_label(data['trench label'])
            if man_obj is not None:
                data['trench uuid'] = man_obj.uuid
        if isinstance(data['trench uuid'], str):
            # we have a trench uuid, check database to get the context path
            data['trench path'] = self.get_subject_context_by_uuid(data['trench uuid'])
        return data
    
    def get_man_obj_by_uuid(self, uuid):
        """ gets a manifest object by uuid """
        try:
            man_obj = Manifest.objects.get(uuid=uuid)
        except Manifest.DoesNotExist:
            man_obj = None
        return man_obj
    
    def get_man_trench_by_label(self, label):
        """ gets a manifest object by uuid """
        man_obj = None
        alt_label = re.sub(r'(\d)\s', r'\1', label)
        labels = [
            label,
            alt_label
        ]
        man_objs = Manifest.objects.filter(project_uuid=self.project_uuid,
                                           class_uri='oc-gen:cat-trench',
                                           label__in=labels)[:1]
        if len(man_objs) > 0:
            man_obj = man_objs[0]
        return man_obj
    
    def get_subject_context_by_uuid(self, uuid):
        """ gets a manifest object by uuid """
        context = None
        try:
            sub_obj = Subject.objects.get(uuid=uuid)
        except Subject.DoesNotExist:
            sub_obj = None
        if sub_obj is not None:
            context = sub_obj.context
        return context
    
    def load_root_index(self):
        """ loads the trench book index, scrapes
            content recursively
        """
        if self.tb_index is None:
            items = self.pc.load_json_file_os_obj(self.pc.pc_directory,
                                                  self.pc.trench_book_index_json)
            if isinstance(items, list):
                self.tb_index = items
    
    def get_locus_files_list(self):
        """ loads the trench book index, scrapes
            content recursively
        """
        if self.locus_files is None:
            files = self.pc.get_directory_files(self.pc.pc_directory)
            if isinstance(files, list):
                self.locus_files = []
                for act_file in files:
                    if 'viewlocus' in act_file:
                        self.locus_files.append(act_file)
        return self.locus_files
    
    def get_str_between_start_end(self, act_str, start_str, end_str):
        """ gets a string value between 1 part and another part of a string """
        output = None
        if len(start_str) < 1 and len(end_str) > 0 and end_str in act_str:
            # we want the start of a string before a delimiter
            end_parts = act_str.split(end_str)
            output = end_parts[0]
        elif len(end_str) < 1 and len(start_str) > 0 and start_str in act_str:
            # we eant the end of a string, after a delimiter
            start_parts = act_str.split(start_str)
            if len(start_parts) > 0:
                output = start_parts[1]
        elif len(start_str) > 0 and len(end_str) > 0:
            if start_str in act_str:
                act_parts = act_str.split(start_str)
                if len(act_parts) > 0:
                    act_part = act_parts[1]
                    if end_str in act_part:
                        end_parts = act_part.split(end_str)
                        output = end_parts[0]
        if isinstance(output, str):
            output = output.replace('\\r', '')
            output = output.replace('\\n', '')
            output = output.replace('\\t', '')
        return output
    
    
    
                