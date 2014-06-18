'''
Handles the exporting of the model to a mxGraph XML file.

    http://jgraph.github.io/mxgraph/javascript/index.html

This XML can then be used as a "codec" by the mxGraph code, to allow for
visualization of the graph in a browser.
'''

from ..model import (ColumnarSchemaObject, Column)
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
            data.mk_table(t)
            for c in t.columns:
                assert isinstance(c, Column)
                data.mk_column(t, c)
                anc = ant.get_column_analysis(c)
                assert isinstance(anc, ColumnAnalysis)
                if anc.foreign_key is not None:
                    foreign_keys.append((t, c, ant, anc))
    
    for fk in foreign_keys:
        (t, c, ant, anc) = fk
        fkc = anc.foreign_key
        assert isinstance(fkc, ProcessedForeignKeyConstraint)
        data.mk_column_link(t.name + '.' + c.name,
                            fkc.fk_table_name + '.' + fkc.fk_column_name)
    
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
        
    def mk_cell(self, parent = None):
        """
        Low level cell creator.  Returns the pair (cell_id, cell Element)
        """
        cell = self.doc.createElement('cell')
        self.root.appendChild(cell)
        cid = self._next_cell_id
        self._next_cell_id += 1
        cell.setAttribute('id', str(cid))
        if parent is None:
            pass
        elif isinstance(parent, int):
            cell.setAttribute('parent', str(parent))
        elif parent in self.tables:
            cell.setAttribute('parent', str(self.tables[parent]))
        elif parent in self.columns:
            cell.setAttribute('parent', str(self.columns[parent]))
        else:
            raise Exception("bad state: " + str(type(parent)) + " (" + str(parent) + ")")
        return (cid, cell)
    
    def mk_table(self, table_obj):
        """
        Make just the table cell, not the columns
        """
        assert isinstance(table_obj, ColumnarSchemaObject)
        
        (cid, cell) = self.mk_cell()
        self.tables[table_obj.name] = cid
        
        cell.setAttribute('kind', 'table')
        cell.setAttribute('name', str(table_obj.name))

        return cell
    
    def mk_column(self, table_obj, column_obj):
        assert isinstance(table_obj, ColumnarSchemaObject)
        assert isinstance(column_obj, Column)
        
        (cid, cell) = self.mk_cell(table_obj.name)
        self.columns[table_obj.name + '.' + column_obj.name] = cid
        cell.setAttribute('kind', 'column')
        cell.setAttribute('name', str(column_obj.name))
        cell.setAttribute('type', str(column_obj.value_type))
        #cell.setAttribute('primaryKey', column_obj.)
        cell.setAttribute('autoIncrement',
              column_obj.auto_increment and '1' or '0')
        return cell
    
    def mk_column_link(self, src_col_name, target_col_name, ltype = None):
        if src_col_name not in self.columns or target_col_name not in self.columns:
            print("No such foreign key: from " + src_col_name + " to " + target_col_name)
            return
        cell = self.mk_cell()[1]
        cell.setAttribute('kind', 'edge')
        cell.setAttribute('source',
            str(self.columns[src_col_name]))
        cell.setAttribute('target',
            str(self.columns[target_col_name]))
        if ltype is not None:
            cell.setAttribute('value', ltype)
        return cell
    
