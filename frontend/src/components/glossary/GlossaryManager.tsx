/**
 * Glossary manager — create, view, delete terminology glossaries.
 */
import { useState, useEffect, useCallback } from 'react';
import { X, Plus, Trash2, ArrowRight } from 'lucide-react';

interface TermPair {
  source: string;
  target: string;
}

interface GlossaryInfo {
  id: string;
  name: string;
  source_lang: string;
  target_lang: string;
  created_at: number;
}

interface GlossaryDetail extends GlossaryInfo {
  terms: TermPair[];
}

interface GlossaryManagerProps {
  open: boolean;
  onClose: () => void;
  backendPort: number | null;
}

export function GlossaryManager({ open, onClose, backendPort }: GlossaryManagerProps) {
  const [glossaries, setGlossaries] = useState<GlossaryInfo[]>([]);
  const [selected, setSelected] = useState<GlossaryDetail | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [terms, setTerms] = useState<TermPair[]>([{ source: '', target: '' }]);
  const [loading, setLoading] = useState(false);

  const api = backendPort ? `http://127.0.0.1:${backendPort}/api/glossaries` : '';

  const loadList = useCallback(async () => {
    if (!api) return;
    const resp = await fetch(api);
    const data = await resp.json();
    setGlossaries(data.glossaries || []);
  }, [api]);

  useEffect(() => { if (open) loadList(); }, [open, loadList]);

  const loadDetail = async (id: string) => {
    setLoading(true);
    const resp = await fetch(`${api}/${id}`);
    const data = await resp.json();
    setSelected(data);
    setLoading(false);
  };

  const handleCreate = async () => {
    if (!name.trim()) return;
    const validTerms = terms.filter((t) => t.source.trim() && t.target.trim());
    const resp = await fetch(api, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, terms: validTerms }),
    });
    if (resp.ok) {
      setShowCreate(false);
      setName('');
      setTerms([{ source: '', target: '' }]);
      loadList();
    }
  };

  const handleDelete = async (id: string) => {
    await fetch(`${api}/${id}`, { method: 'DELETE' });
    setSelected(null);
    loadList();
  };

  const addTerm = () => setTerms((t) => [...t, { source: '', target: '' }]);
  const removeTerm = (i: number) => setTerms((t) => t.filter((_, j) => j !== i));
  const updateTerm = (i: number, field: 'source' | 'target', val: string) =>
    setTerms((t) => t.map((term, j) => (j === i ? { ...term, [field]: val } : term)));

  if (!open) return null;

  return (
    <div className="history-overlay" onClick={onClose}>
      <div className="glossary-panel" onClick={(e) => e.stopPropagation()}>
        <div className="glossary-panel__header">
          <h2 className="history-panel__title">术语管理</h2>
          <button type="button" className="history-panel__close" onClick={onClose} aria-label="关闭">
            <X size={16} strokeWidth={2} />
          </button>
        </div>

        <div className="glossary-panel__body">
          {/* Create button */}
          {!showCreate && !selected && (
            <button type="button" className="glossary-add-btn" onClick={() => setShowCreate(true)}>
              <Plus size={16} strokeWidth={2} />
              新建术语表
            </button>
          )}

          {/* Create form */}
          {showCreate && (
            <div className="glossary-create">
              <input type="text" className="settings-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="术语表名称" />
              {terms.map((t, i) => (
                <div key={i} className="glossary-term-row">
                  <input type="text" className="settings-input" value={t.source} onChange={(e) => updateTerm(i, 'source', e.target.value)} placeholder="原文" />
                  <ArrowRight size={14} strokeWidth={1.5} className="glossary-arrow" />
                  <input type="text" className="settings-input" value={t.target} onChange={(e) => updateTerm(i, 'target', e.target.value)} placeholder="译文" />
                  {terms.length > 1 && (
                    <button type="button" className="glossary-term-del" onClick={() => removeTerm(i)} aria-label="移除术语">
                      <X size={14} strokeWidth={2} />
                    </button>
                  )}
                </div>
              ))}
              <div className="glossary-create__actions">
                <button type="button" className="test-btn" onClick={addTerm}>
                  <Plus size={14} strokeWidth={2} />
                  添加术语
                </button>
                <button type="button" className="control-btn control-btn--start" onClick={handleCreate} disabled={!name.trim()}>创建</button>
                <button type="button" className="test-btn" onClick={() => setShowCreate(false)}>取消</button>
              </div>
            </div>
          )}

          {/* Detail view */}
          {loading && <p className="history-loading">加载中...</p>}
          {selected && (
            <div className="glossary-detail">
              <div className="glossary-detail__header">
                <button type="button" className="history-back" onClick={() => setSelected(null)}>← 返回</button>
                <h3>{selected.name}</h3>
                <button type="button" className="glossary-delete-btn" onClick={() => handleDelete(selected.id)}>
                  <Trash2 size={11} strokeWidth={2} />
                  删除
                </button>
              </div>
              <div className="glossary-detail__terms">
                {selected.terms.map((t, i) => (
                  <div key={i} className="glossary-term-item">
                    <span className="glossary-term-item__source">{t.source}</span>
                    <ArrowRight size={12} strokeWidth={1.5} className="glossary-arrow" />
                    <span className="glossary-term-item__target">{t.target}</span>
                  </div>
                ))}
                {selected.terms.length === 0 && <p className="history-hint">暂无术语</p>}
              </div>
            </div>
          )}

          {/* List */}
          {!showCreate && !selected && (
            <div className="glossary-list">
              {glossaries.length === 0 && <p className="history-hint">暂无术语表，点击上方按钮创建</p>}
              {glossaries.map((g) => (
                <div key={g.id} className="glossary-list-item" onClick={() => loadDetail(g.id)}>
                  <span className="glossary-list-item__name">{g.name}</span>
                  <span className="glossary-list-item__meta">{g.source_lang}→{g.target_lang}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
