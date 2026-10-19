import React, { useEffect, useState } from 'react'
import EcgCard from './EcgCard'
import BloodPressureCard from './BloodPressureCard'
import HistoryCard from './HistoryCard'
import jsPDF from 'jspdf'
import autoTable from 'jspdf-autotable'
import { API_BASE } from '../config/api'

export default function DashboardSection() {
    const [workloadForm, setWorkloadForm] = useState({
        access_frequency: 0.00,
        reuse_distance: 0.00,
        temporal_locality: 0.00,
        spatial_locality: 0.00,
    })

    const [policyResult, setPolicyResult] = useState(null)
    const [history, setHistory] = useState([])
    const [loading, setLoading] = useState(false)
    const [historyLoading, setHistoryLoading] = useState(false)
    const [error, setError] = useState('')
    const [file, setFile] = useState(null)
    const [refreshTrigger, setRefreshTrigger] = useState(Date.now())

    const handleChange = (field, val) => {
        // Strict 0-1 range enforcement
        const numericVal = Math.min(1, Math.max(0, val))
        setWorkloadForm(prev => ({
            ...prev,
            [field]: numericVal
        }))
    }



    const fetchHistory = async () => {
        setHistoryLoading(true)
        try {
            const res = await fetch(`${API_BASE}/policy_history`)
            if (res.ok) {
                const data = await res.json()
                setHistory(data)
            }
        } catch (e) {
            console.error('Failed to fetch history', e)
        } finally {
            setHistoryLoading(false)
        }
    }

    useEffect(() => {
        fetchHistory()
        // One-time load for results coming from the Upload page
        const stored = sessionStorage.getItem('cachex:lastPrediction')
        if (stored) {
            try {
                const parsed = JSON.parse(stored)
                setPolicyResult(parsed)
                if (parsed.extracted_features) {
                    setWorkloadForm(parsed.extracted_features)
                }
                // Clear immediately so a refresh or direct visit starts at 0
                sessionStorage.removeItem('cachex:lastPrediction')
            } catch (e) {
                console.error('Failed to parse one-time prediction', e)
            }
        }
    }, [])

    const handleSubmit = async (e) => {
        e.preventDefault()
        setLoading(true)
        setError('')

        try {
            // 1. Upload Workload Features
            const uploadRes = await fetch(`${API_BASE}/upload_workload`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(workloadForm),
            })

            if (!uploadRes.ok) {
                throw new Error('Failed to upload workload features')
            }

            const { workload_id } = await uploadRes.json()

            // 2. Trigger ML Analysis
            const analyzeRes = await fetch(`${API_BASE}/analyze_workload?workload_id=${workload_id}`, {
                method: 'POST',
            })

            if (!analyzeRes.ok) {
                throw new Error('Failed to get policy prediction from ML model')
            }

            const data = await analyzeRes.json()

            // Store and show result
            setPolicyResult(data)
            sessionStorage.setItem('cachex:lastPrediction', JSON.stringify(data))
            fetchHistory()
            setRefreshTrigger(Date.now())
        } catch (err) {
            setError(err.message || 'Something went wrong')
        } finally {
            setLoading(false)
        }
    }

    const handleDownloadPDF = () => {
        if (!policyResult) return;

        const doc = new jsPDF();
        
        // Title
        doc.setFontSize(22);
        doc.setTextColor(30, 58, 138); // blue-900
        doc.text("CacheX Engineers Policy Optimization Report", 14, 22);
        
        // Subtitle / Date
        doc.setFontSize(11);
        doc.setTextColor(100, 116, 139); // slate-500
        const dateStr = policyResult.created_at || new Date().toLocaleString();
        doc.text(`Generated on: ${dateStr}`, 14, 30);
        
        // Workload ID
        doc.setFontSize(14);
        doc.setTextColor(15, 23, 42); // slate-900
        doc.text(`Workload ID: ${policyResult.workload_id || 'LOCAL-SIM'}`, 14, 45);

        // Core Metrics Table
        autoTable(doc, {
            startY: 55,
            head: [['Metric', 'Value']],
            body: [
                ['Optimized Engine Policy', policyResult.predicted_policy || '—'],
                ['Model Confidence', policyResult.confidence != null ? `${(policyResult.confidence * 100).toFixed(0)}%` : '—'],
                ['Latency Gain', `${policyResult.latency_gain || 0}ms`],
                ['Throughput', `${((policyResult.throughput_gain || 0) >= 0 ? '+' : '')}${policyResult.throughput_gain || 0}%`]
            ],
            theme: 'grid',
            headStyles: { fillColor: [37, 99, 235] }, // blue-600
            styles: { fontSize: 12, cellPadding: 5 }
        });

        // Extracted Features Table
        if (policyResult.extracted_features) {
            doc.text("Extracted Workload Features (Calculated Averages)", 14, doc.lastAutoTable.finalY + 15);
            const featureBody = Object.entries(policyResult.extracted_features).map(([k, v]) => [
                k.replace('_', ' ').toUpperCase(),
                typeof v === 'number' ? v.toFixed(4) : v
            ]);
            
            autoTable(doc, {
                startY: doc.lastAutoTable.finalY + 20,
                head: [['Feature', 'Average Value']],
                body: featureBody,
                theme: 'striped',
                headStyles: { fillColor: [71, 85, 105] }, // slate-600
                styles: { fontSize: 10, cellPadding: 4 }
            });
        }

        // Neural Reasoning Insights
        if (Array.isArray(policyResult.reason) && policyResult.reason.length > 0) {
            let currentY = doc.lastAutoTable ? doc.lastAutoTable.finalY + 15 : 100;
            
            // Avoid page break issue
            if (currentY > 250) {
                doc.addPage();
                currentY = 20;
            }

            doc.setFontSize(14);
            doc.setTextColor(15, 23, 42);
            doc.text("Neural Reasoning & Insights", 14, currentY);
            
            doc.setFontSize(11);
            doc.setTextColor(71, 85, 105);
            let reasonY = currentY + 10;
            
            policyResult.reason.forEach((reason, idx) => {
                const textLines = doc.splitTextToSize(`${idx + 1}. ${reason}`, 180);
                
                if (reasonY + (textLines.length * 7) > 280) {
                    doc.addPage();
                    reasonY = 20;
                }
                
                doc.text(textLines, 14, reasonY);
                reasonY += (textLines.length * 7);
            });
        }
        
        // Footer
        const pageCount = doc.internal.getNumberOfPages();
        for (let i = 1; i <= pageCount; i++) {
            doc.setPage(i);
            doc.setFontSize(10);
            doc.setTextColor(148, 163, 184);
            doc.text(
                `Page ${i} of ${pageCount} - CacheX Engineers Adaptive Cache Optimization`,
                14,
                doc.internal.pageSize.height - 10
            );
        }

        doc.save(`CacheX_Report_${policyResult.workload_id || 'sim'}.pdf`);
    }

    return (
        <section id="solutions" className="pb-12">
            <div className="grid grid-cols-1 xl:grid-cols-12 gap-8 items-start">
                {/* LEFT: Live metric cards */}
                <div className="xl:col-span-4 flex flex-col gap-8 animate-slide-up" style={{ animationDelay: '0.15s' }}>
                    <EcgCard isIdle={!policyResult} refreshTrigger={refreshTrigger} />
                    <BloodPressureCard isIdle={!policyResult} refreshTrigger={refreshTrigger} />
                    <HistoryCard
                        history={history}
                        loading={historyLoading}
                        onRefresh={fetchHistory}
                    />
                </div>

                {/* RIGHT: Workload form + policy and history */}
                <div className="xl:col-span-8 flex flex-col gap-8 animate-slide-up" style={{ animationDelay: '0.2s' }}>
                    {/* Workload configuration & prediction */}
                    <div className="bg-white/40 backdrop-blur-xl rounded-[3rem] shadow-2xl shadow-indigo-900/5 border border-white/60 p-8 md:p-12">
                        <div className="flex flex-wrap items-center justify-between gap-6 mb-10">
                            <div className="flex flex-col gap-2">
                                <div className="w-10 h-1 bg-blue-600 rounded-full"></div>
                                <h2 className="text-2xl md:text-3xl font-black text-slate-900 tracking-tight">
                                    Policy Orchestration
                                </h2>
                            </div>
                            <div className="flex items-center gap-3">
                                {policyResult && (
                                    <>
                                        <button
                                            onClick={handleDownloadPDF}
                                            type="button"
                                            className="px-4 py-2 bg-emerald-500 text-white hover:bg-emerald-600 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-lg flex items-center gap-2"
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                                                <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
                                            </svg>
                                            Download Report
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => {
                                                sessionStorage.removeItem('cachex:lastPrediction')
                                                setPolicyResult(null)
                                                setWorkloadForm({
                                                    access_frequency: 0.00,
                                                    reuse_distance: 0.00,
                                                    temporal_locality: 0.00,
                                                    spatial_locality: 0.00,
                                                })
                                            }}
                                            className="px-4 py-2 border border-slate-200 text-slate-500 hover:text-slate-900 hover:border-slate-900 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all"
                                        >
                                            Clear Analysis
                                        </button>
                                    </>
                                )}
                                <div className="px-4 py-2 bg-slate-900 text-white rounded-xl shadow-xl">
                                    <span className="text-[10px] font-black uppercase tracking-[0.2em]">Neural Engine active</span>
                                </div>
                            </div>
                        </div>

                        <form className="grid grid-cols-1 gap-10" onSubmit={handleSubmit}>
                            <div className="space-y-8">
                                <div className="grid grid-cols-2 gap-6">
                                    {[
                                        { label: 'Access Frequency', field: 'access_frequency' },
                                        { label: 'Reuse Distance', field: 'reuse_distance' },
                                        { label: 'Temporal Locality', field: 'temporal_locality' },
                                        { label: 'Spatial Locality', field: 'spatial_locality' },
                                    ].map((item) => (
                                        <div key={item.field} className="space-y-2">
                                            <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest">
                                                {item.label}
                                            </label>
                                            <input
                                                type="number"
                                                min="0"
                                                max="1"
                                                step="0.01"
                                                className="w-full rounded-2xl border border-white/60 px-4 py-4 text-sm font-bold text-slate-900 bg-white/50 focus:outline-none focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all font-mono"
                                                value={workloadForm[item.field]}
                                                onChange={(e) =>
                                                    handleChange(item.field, parseFloat(e.target.value) || 0)
                                                }
                                            />
                                        </div>
                                    ))}
                                </div>
                                <div className="flex justify-end mt-4">
                                    <button
                                        type="submit"
                                        disabled={loading}
                                        className={`px-8 py-4 rounded-2xl font-black uppercase tracking-widest transition-all shadow-xl flex items-center gap-3 ${loading ? 'bg-slate-200 text-slate-400 cursor-not-allowed' : 'bg-blue-600 text-white hover:bg-blue-700 hover:scale-105 active:scale-95 shadow-blue-500/20'}`}
                                    >
                                        {loading ? (
                                            <>
                                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                                Analyzing...
                                            </>
                                        ) : (
                                            <>
                                                <svg viewBox="0 0 24 24" className="w-4 h-4 fill-none stroke-current stroke-[3]">
                                                    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                                                </svg>
                                                Analyze Parameters
                                            </>
                                        )}
                                    </button>
                                </div>
                            </div>

                            <div className="flex flex-col gap-6">
                                <div className={`transition-all duration-700 ${policyResult ? 'bg-slate-900' : 'bg-slate-800/50'} text-white rounded-[2.5rem] p-8 md:p-10 shadow-3xl relative overflow-hidden group`}>
                                    <div className="absolute top-0 right-0 w-64 h-64 bg-blue-600/10 rounded-full -translate-y-1/2 translate-x-1/2 blur-3xl group-hover:bg-blue-600/20 transition-all duration-1000"></div>

                                    <div className="relative flex items-center justify-between mb-8">
                                        <div className="flex items-center gap-3">
                                            <div className={`w-3 h-3 rounded-full ${policyResult ? 'bg-emerald-500 animate-pulse' : 'bg-slate-600'}`}></div>
                                            <p className="text-[10px] font-black text-blue-400 uppercase tracking-[0.2em]">
                                                {policyResult ? 'Optimization Successful' : 'Awaiting Telemetry'}
                                            </p>
                                        </div>
                                        {policyResult && (
                                            <span className="text-[10px] font-black text-white/40 uppercase tracking-widest bg-white/5 px-3 py-1 rounded-lg">
                                                ID: {policyResult.workload_id || 'LOCAL-SIM'}
                                            </span>
                                        )}
                                    </div>

                                    {policyResult ? (
                                        <div className="relative space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-1000">
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                                <div className="space-y-1">
                                                    <p className="text-xs text-white/40 font-black uppercase tracking-widest">Optimized Engine Policy</p>
                                                    <p className="text-4xl md:text-5xl font-black tracking-tighter italic text-white drop-shadow-2xl">
                                                        {policyResult.predicted_policy || '—'}
                                                    </p>
                                                </div>
                                                <div className="flex flex-col md:items-end justify-center">
                                                    <p className="text-xs text-white/40 font-black uppercase tracking-widest mb-1">Model Confidence</p>
                                                    <div className="flex items-baseline gap-2">
                                                        <p className="text-5xl font-black text-emerald-400 tracking-tighter">
                                                            {policyResult.confidence != null
                                                                ? `${(policyResult.confidence * 100).toFixed(0)}`
                                                                : '—'}
                                                        </p>
                                                        <span className="text-xl font-black text-emerald-400/50">%</span>
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="grid grid-cols-3 gap-4 pt-8 border-t border-white/50">
                                                {[
                                                    { label: 'Analysis Date', value: policyResult.created_at || 'JUST NOW' },
                                                    { label: 'Latency Gain', value: `${policyResult.latency_gain}ms` },
                                                    { label: 'Throughput', value: `${(policyResult.throughput_gain >= 0 ? '+' : '')}${policyResult.throughput_gain}%` },
                                                ].map((stat) => (
                                                    <div key={stat.label} className="p-4 rounded-2xl bg-white/5 border border-white/10">
                                                        <p className="text-[8px] font-black text-white/30 uppercase tracking-[0.2em] mb-1">{stat.label}</p>
                                                        <p className="text-sm font-black text-blue-400 font-mono">{stat.value}</p>
                                                    </div>
                                                ))}
                                            </div>

                                            {Array.isArray(policyResult.reason) && (
                                                <div className="space-y-3">
                                                    <p className="text-[10px] font-black text-white/30 uppercase tracking-widest">Neural Reasoning & Insights</p>

                                                    {policyResult.extracted_features && (
                                                        <div className="p-3 rounded-xl bg-white/5 border border-white/10 mb-2">
                                                            <p className="text-[8px] font-black text-blue-400 uppercase tracking-widest mb-2">Calculated CSV Averages</p>
                                                            <div className="grid grid-cols-4 gap-2">
                                                                {Object.entries(policyResult.extracted_features).map(([k, v]) => (
                                                                    <div key={k}>
                                                                        <p className="text-[7px] text-white/40 uppercase mb-1 truncate">{k.replace('_', ' ')}</p>
                                                                        <p className="text-[10px] font-bold text-white">{v.toFixed(3)}</p>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}

                                                    <div className="grid grid-cols-1 gap-2">
                                                        {policyResult.reason.slice(0, 3).map((r, idx) => (
                                                            <div key={idx} className="flex gap-4 p-4 rounded-xl bg-blue-600/5 border border-blue-600/10 text-xs font-medium text-white/80 group/item hover:bg-blue-600/10 transition-colors">
                                                                <span className="flex-shrink-0 w-5 h-5 rounded-lg bg-blue-600/20 text-blue-400 flex items-center justify-center font-black text-[10px]">
                                                                    0{idx + 1}
                                                                </span>
                                                                {r}
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    ) : (
                                        <div className="relative py-12 flex flex-col items-center justify-center text-center gap-6">
                                            <div className="w-16 h-16 rounded-full border-4 border-dashed border-blue-600/20 flex items-center justify-center">
                                                <div className="w-8 h-8 rounded-full bg-blue-600/10"></div>
                                            </div>
                                            <div className="space-y-2">
                                                <p className="text-sm text-white font-bold">Awaiting Telemetry</p>
                                                <p className="text-[10px] text-white/40 leading-relaxed font-medium max-w-xs">
                                                    Initialize system parameters or ingest telemetry data to activate the policy regression model.
                                                </p>
                                            </div>
                                        </div>
                                    )}
                                </div>


                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </section>
    )
}

