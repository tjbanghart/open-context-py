import uuid as GenUUID
import datetime
from django.db import models
from django.db.models import Q
from opencontext_py.apps.imports.sources.models import ImportSource
from opencontext_py.apps.imports.fields.models import ImportField
from opencontext_py.apps.imports.records.models import ImportCell
from opencontext_py.apps.imports.records.create import ImportRecords
from opencontext_py.apps.imports.fields.create import ImportFields
from opencontext_py.apps.imports.refine.api import RefineAPI


# Imports records, doing the appropriate lookups for uuids
class ImportRefineSource():

    def __init__(self):
        self.source_id = False
        self.refine_project = False
        self.obsolete_source_id = False
        self.project_uuid = False
        self.related_fields = {}
        self.imp_source_obj = False
        self.row_count = False
        self.do_batch = True

    def gen_obsolete_source_id(self):
        self.obsolete_source_id = 'obs-' + self.source_id

    def import_refine_to_project(self,
                                 refine_project,
                                 project_uuid):
        """ Imports data from refine.
            The start of each batch is determined by a
            database call.

            This defaults to importing in batches,
            but 
        """
        self.project_uuid = project_uuid
        start = False
        last_row = False
        r_api = RefineAPI(refine_project)
        self.source_id = r_api.source_id
        self.gen_obsolete_source_id()
        imp_f = ImportFields()
        imp_f.source_id = self.source_id
        imp_f.project_uuid = self.project_uuid
        imp_r = ImportRecords()
        imp_r.source_id = self.source_id
        imp_r.project_uuid = self.project_uuid
        imp_r.obsolete_source_id = self.obsolete_source_id
        imp_r.do_batch = self.do_batch
        # check to see if refine is active by asking for the project schema
        schema_ok = imp_f.get_refine_schema(refine_project)
        if schema_ok:
            start = self.get_max_row_num()
            # ok, refine works, schema is OK. Save old project data as obsolute source_id
            if start == 0:
                self.create_new_refine_source()
                self.update_obsolete_source()
                # now save the current schema for this project
                imp_f.obsolete_source_id = self.obsolete_source_id
                model_ok = imp_f.save_refine_model(refine_project)
                if model_ok:
                    # now that we've save the current schema, get+save the project records
                    last_row = imp_r.save_refine_records(refine_project, start)
            else:
                if start < self.row_count:
                    # save the batch of refine records
                    last_row = imp_r.save_refine_records(refine_project, start)
                else:
                    last_row = self.row_count
        if last_row >= self.row_count:
            self.imp_source_obj.imp_status = 'preparation'
            self.imp_source.save()
            self.make_or_preserve_obsolete_uuids()
            self.delete_obsolete_source()
        output = {'refine': refine_project,
                  'row_count': self.row_count,
                  'batch_size': r_api.row_request_limit,
                  'start': start,
                  'end': last_row}
        return output

    def update_obsolete_source(self):
        """ Changes an old import to have a different source_id
            so that we can retain previously assigned uuids
        """
        ImportCell.objects\
                  .filter(source_id=self.source_id)\
                  .update(source_id=self.obsolete_source_id)
        ImportField.objects\
                   .filter(source_id=self.source_id)\
                   .update(source_id=self.obsolete_source_id)

    def delete_obsolete_source(self):
        """ Deletes the obsolte import """
        ImportCell.objects\
                  .filter(source_id=self.obsolete_source_id)\
                  .delete()
        ImportField.objects\
                   .filter(source_id=self.obsolete_source_id)\
                   .delete()

    def make_or_preserve_obsolete_uuids(self):
        """ Makes uuids, considering obsolete uuids 
        """
        w_fields = ImportField.objects\
                              .filter(source_id=self.source_id)
        for imp_field in w_fields:
            field_num = imp_field.field_num
            print('Applying uuids to field: ' + str(field_num))
            w_cells = ImportCell.objects\
                                .filter(source_id=self.source_id,
                                        field_num=field_num)\
                                .iterator()
            for imp_cell in w_cells:
                imp_cell.fl_uuid = self.get_make_field_literal_uuid(field_num,
                                                                    imp_cell.record)
                imp_cell.l_uuid = self.get_make_literal_uuid(imp_cell.record)
                imp_cell.uuids_save()

    def get_make_literal_uuid(self, record):
        """ Gets a uuid for a literal in an import table,
            where a literal has a unique uuid with a project's import records
        """
        l_uuid = self.get_literal_uuid(record)
        if l_uuid is False:
            l_uuid = GenUUID.uuid4()
        return l_uuid

    def get_make_field_literal_uuid(self, field_num, record):
        """ Gets or makes a uuid for unique to the field and a project
        """
        fl_uuid = self.get_field_literal_uuid(field_num, record)
        if fl_uuid is False:
            fl_uuid = GenUUID.uuid4()
        return fl_uuid

    def get_field_literal_uuid(self, field_num, record):
        """ Gets a uuid for a literal of the same in a given field
            in a project
        """
        rec_hash = self.get_record_hash(record)
        # print('Checking fl rec_hash: ' + rec_hash)
        output = False
        rel_fields = self.get_related_fields(field_num)
        if len(rel_fields) > 0:
            l_tables = 'imp_records'
            filters = ''
            for rel_field in rel_fields:
                act_filter = '(imp_records.source_id = \'' + str(rel_field.source_id) + '\' '
                act_filter += 'AND imp_records.field_num = \'' + str(rel_field.field_num) + '\')'
                if filters == '':
                    filters = act_filter
                else:
                    filters += ' OR ' + act_filter
            check = ImportCell.objects\
                              .filter(project_uuid=self.project_uuid,
                                      rec_hash=rec_hash)\
                              .exclude(fl_uuid=str(False))\
                              .extra(where=[filters])[:1]
            if len(check) > 0:
                output = check[0].fl_uuid
                if output == str(False):
                    output = False
        return output

    def get_field_uuid(self, field_num):
        """ Gets the f_uuid (field_uuid) associated with a field_num """
        output = False
        field_look = ImportField.objects\
                                .filter(Q(source_id=self.source_id) | Q(source_id=self.obsolete_source_id),
                                        field_num=field_num)[:1]
        if len(field_look) > 0:
            output = field_look[0].f_uuid
            if output == str(False):
                output = False
        return output

    def get_related_fields(self, field_num):
        """ Gets imp_field objects for fields that share the
            same f_uuid
        """
        if field_num in self.related_fields:
            rel_fields = self.related_fields[field_num]
        else:
            field_uuid = self.get_field_uuid(field_num)
            rel_fields = ImportField.objects\
                                    .filter(f_uuid=field_uuid)
            self.related_fields[field_num] = rel_fields
        return rel_fields

    def get_literal_uuid(self, record):
        """ Gets a uuid for a literal in a project's import records """
        rec_hash = self.get_record_hash(record)
        output = False
        check = ImportCell.objects\
                          .filter(project_uuid=self.project_uuid,
                                  rec_hash=rec_hash)\
                          .exclude(l_uuid=str(False))[:1]
        if len(check) > 0:
            output = check[0].l_uuid
            if output == str(False):
                output = False
        return output

    def get_record_hash(self, record):
        """ Gets the hash value for a record given the current project_uuid """
        imp_c = ImportCell()
        rec_hash = imp_c.make_rec_hash(self.project_uuid,
                                       record)
        return str(rec_hash)

    def get_max_row_num(self):
        """ Gets the current maximum row number loaded from refine source """
        max_row = 0
        max_rec = ImportCell.objects\
                            .filter(source_id=self.source_id)\
                            .order_by('-row_num')[:1]
        if len(max_rec) > 0:
            max_row = max_rec[0]['row_num']
        return max_row

    def get_refine_source_meta(self):
        """ Gets the metadata for a Refine source from the database """
        try:
            self.imp_source_obj = ImportSource.objects.get(source_id=self.source_id)
            self.row_count = self.imp_source_obj.row_count
        except ImportSource.DoesNotExist:
            self.imp_source_obj = False

    def create_new_refine_source(self):
        """ Saves a record of a new Refine data source """
        r_api = RefineAPI(self.refine_project)
        meta = r_api.get_metadata()
        size = r_api.get_size()
        if meta is not False and size is not False:
            imp_s = ImportSource
            imp_s.source_id = self.source_id
            imp_s.project_uuid = self.project_uuid
            imp_s.label = meta['name']
            imp_s.field_count = size['field_count']
            imp_s.row_count = size['row_count']
            imp_s.source_type = 'refine'
            imp_s.is_current = True
            imp_s.imp_status = 'loading'
            imp_s.save()
            self.imp_source_obj = imp_s
            self.row_count = imp_s.row_count
