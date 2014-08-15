'''
Converts the model to an XML format that can be used to generate a graph.
'''

from ..model import (ColumnarSchemaObject, Column, View, Table)
from . import (AnalysisModel, ColumnSetAnalysis, ColumnAnalysis,
               ProcessedForeignKeyConstraint)
from xml.dom.minidom import getDOMImplementation

def generate_graph_xml(amodel):
    assert isinstance(amodel, AnalysisModel)
    data = GraphData()
    
    foreign_keys = []
    for t in amodel.schemas:
        ant = amodel.get_analysis_for(t)
        assert isinstance(ant, ColumnSetAnalysis)
        if isinstance(t, ColumnarSchemaObject):
            t_el = data.mk_table(t)
            for c in t.columns:
                assert isinstance(c, Column)
                anc = ant.get_column_analysis(c)
                data.mk_column(t_el, t, anc)
                assert isinstance(anc, ColumnAnalysis)
                if anc.foreign_key is not None:
                    foreign_keys.append((t, c, ant, anc))
    
    for fk in foreign_keys:
        (t, c, ant, anc) = fk
        fkc = anc.foreign_key
        assert isinstance(fkc, ProcessedForeignKeyConstraint)
        foreign_table = amodel.get_schema_named(fkc.fk_table_name)
        if foreign_table is None:
            print("No foreign table " + fkc.fk_table_name + ", referenced in " +
                  t.name + "." + c.name)
            continue
        assert isinstance(foreign_table, ColumnarSchemaObject)
        fta = amodel.get_analysis_for(foreign_table)
        assert isinstance(fta, ColumnSetAnalysis)
        foreign_column = fta.get_column_analysis(fkc.fk_column_name)
        if foreign_column is None:
            print("No foreign column " + fkc.fk_table_name + "." +
                  fkc.fk_column_name + ", referenced in " +
                  t.name + "." + c.name)
            continue
        assert isinstance(foreign_column, ColumnAnalysis)
        data.mk_column_link(amodel.get_analysis_for(t), anc, fta, foreign_column)
    
    return data.doc.toxml('UTF-8')


class GraphData(object):
    def __init__(self):
        object.__init__(self)
        self.doc = getDOMImplementation().createDocument(
             None, "schemagraph", None)
        self.root = self.doc.documentElement
        self.tables = {}
        self.columns = {}
        
        self._next_cell_id = 0
    
    def _mk_basic(self, name, parent = None):
        if parent is None:
            parent = self.root
        el = self.doc.createElement(name)
        parent.appendChild(el)
        cid = self._next_cell_id
        self._next_cell_id += 1
        el.setAttribute('id', str(cid))
        return (cid, el)
    
    def mk_table(self, table_obj):
        """
        Make just the table cell, not the columns
        """
        assert isinstance(table_obj, ColumnarSchemaObject)
        
        (cid, el) = self._mk_basic('table')
        self.tables[table_obj] = cid
        
        el.setAttribute('name', str(table_obj.name))
        if isinstance(table_obj, View):
            el.setAttribute('kind', 'view')
        elif isinstance(table_obj, Table):
            el.setAttribute('kind', 'table')
        else:
            raise Exception("unknown type " + str(type(table_obj)))

        return el
    
    def mk_column(self, parent_el, table_obj, column_obj):
        assert isinstance(table_obj, ColumnarSchemaObject)
        assert isinstance(column_obj, ColumnAnalysis)
        
        (cid, el) = self._mk_basic('column', parent_el)
        self.columns[column_obj] = cid
        
        el.setAttribute('name', str(column_obj.sql_name))
        el.setAttribute('type', str(column_obj.schema.value_type))
        el.setAttribute('primaryKey',
              column_obj.is_primary_key and '1' or '0')
        el.setAttribute('autoIncrement',
              column_obj.schema.auto_increment and '1' or '0')
        return el
    
    def mk_column_link(self, src_table, src_col, target_table, target_col, ltype = None):
        assert isinstance(src_table, ColumnSetAnalysis)
        assert isinstance(src_col, ColumnAnalysis)
        assert isinstance(target_table, ColumnSetAnalysis)
        assert isinstance(target_col, ColumnAnalysis)
        
        if src_col not in self.columns or target_col not in self.columns:
            print("No such foreign key: from " + src_col.sql_name + " to " +
                  target_col.sql_name)
            return
        
        src_id = self.columns[src_col]
        target_id = self.columns[target_col]
        
        el = self._mk_basic('edge')[1]
        el.setAttribute('source', str(src_id))
        el.setAttribute('target', str(target_id))
        if ltype is not None:
            el.setAttribute('name', ltype)
        return el
