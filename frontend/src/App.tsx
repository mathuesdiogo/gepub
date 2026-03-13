import { useMemo, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import * as Select from '@radix-ui/react-select'
import * as Tabs from '@radix-ui/react-tabs'
import * as Tooltip from '@radix-ui/react-tooltip'
import { useQuery } from '@tanstack/react-query'
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip as ChartTooltip,
} from 'chart.js'
import { zodResolver } from '@hookform/resolvers/zod'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import {
  AlertCircle,
  ChartNoAxesColumn,
  Check,
  ChevronDown,
  Circle,
  Mail,
  Search,
  Settings2,
  Sparkles,
  Table as TableIcon,
} from 'lucide-react'
import { Bar } from 'react-chartjs-2'
import { useForm, useWatch } from 'react-hook-form'
import {
  Cell,
  CartesianGrid,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Legend as RechartsLegend,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { z } from 'zod'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

ChartJS.register(CategoryScale, LinearScale, BarElement, ChartTooltip, Legend)

interface Kpis {
  municipios: number
  secretarias: number
  unidades: number
  modulos: number
}

interface TimelinePoint {
  mes: string
  total: number
}

interface GroupPoint {
  nome: string
  total: number
}

interface MunicipioOption {
  id: number
  nome: string
  uf: string
}

interface OverviewResponse {
  kpis: Kpis
  timeline: TimelinePoint[]
  top_modulos: GroupPoint[]
  distribuicao_tipos: GroupPoint[]
  municipios: MunicipioOption[]
}

interface SecretariaRow {
  id: number
  nome: string
  sigla: string
  tipo_modelo: string
  ativo: boolean
  municipio_id: number
  municipio_nome: string
  apps_ativos: string[]
}

interface SecretariasResponse {
  count: number
  next: string | null
  previous: string | null
  results: SecretariaRow[]
}

const onboardingSchema = z.object({
  municipio: z.string().min(3, 'Informe o nome do município.'),
  responsavel: z.string().min(3, 'Informe o nome do responsável.'),
  email: z.string().email('Informe um e-mail válido.'),
  telefone: z.string().min(10, 'Informe um telefone válido.'),
  modulos: z.array(z.string()).min(1, 'Selecione pelo menos um módulo.'),
  inicio: z.enum(['imediato', '7-dias', '15-dias']),
})

type OnboardingInput = z.infer<typeof onboardingSchema>

const moduloCatalog = [
  {
    id: 'educacao',
    title: 'Educação',
    description: 'Diário • Matrículas • Indicadores',
  },
  {
    id: 'saude',
    title: 'Saúde',
    description: 'Regulação • Prontuário • Painéis',
  },
  {
    id: 'administracao',
    title: 'Administração',
    description: 'Processos • Contratos • Compras',
  },
  {
    id: 'portal-cidadao',
    title: 'Portal do Cidadão',
    description: 'Serviços digitais e protocolos',
  },
] as const

async function fetchOverview(municipioId?: number): Promise<OverviewResponse> {
  const params = new URLSearchParams()
  if (municipioId) {
    params.set('municipio', String(municipioId))
  }

  const response = await fetch(`/api/frontend/overview/?${params.toString()}`, {
    credentials: 'include',
  })

  if (!response.ok) {
    throw new Error('Falha ao carregar visão geral da plataforma.')
  }

  return (await response.json()) as OverviewResponse
}

async function fetchSecretarias(filters: {
  municipioId?: number
  ativo: 'todos' | 'ativos' | 'inativos'
  search: string
}): Promise<SecretariasResponse> {
  const params = new URLSearchParams()
  params.set('page_size', '100')

  if (filters.municipioId) {
    params.set('municipio_id', String(filters.municipioId))
  }

  if (filters.ativo !== 'todos') {
    params.set('ativo', filters.ativo === 'ativos' ? 'true' : 'false')
  }

  if (filters.search.trim()) {
    params.set('search', filters.search.trim())
  }

  const response = await fetch(`/api/frontend/secretarias/?${params.toString()}`, {
    credentials: 'include',
  })

  if (!response.ok) {
    throw new Error('Falha ao carregar secretarias.')
  }

  return (await response.json()) as SecretariasResponse
}

function montarContatoMailto(payload: OnboardingInput | null): string {
  if (!payload) {
    return 'mailto:contato@gepub.com.br'
  }

  const subject = encodeURIComponent(`Onboarding GEPUB - ${payload.municipio}`)
  const body = encodeURIComponent(
    [
      `Município: ${payload.municipio}`,
      `Responsável: ${payload.responsavel}`,
      `E-mail: ${payload.email}`,
      `Telefone: ${payload.telefone}`,
      `Módulos: ${payload.modulos.join(', ')}`,
      `Início desejado: ${payload.inicio}`,
    ].join('\n'),
  )

  return `mailto:contato@gepub.com.br?subject=${subject}&body=${body}`
}

function App() {
  const [municipioFilter, setMunicipioFilter] = useState<string>('todos')
  const [statusFilter, setStatusFilter] = useState<'todos' | 'ativos' | 'inativos'>('todos')
  const [searchTerm, setSearchTerm] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [payloadPreview, setPayloadPreview] = useState<OnboardingInput | null>(null)

  const municipioId = municipioFilter === 'todos' ? undefined : Number(municipioFilter)

  const overviewQuery = useQuery({
    queryKey: ['frontend-overview', municipioId],
    queryFn: () => fetchOverview(municipioId),
    staleTime: 60_000,
  })

  const secretariasQuery = useQuery({
    queryKey: ['frontend-secretarias', municipioId, statusFilter, searchTerm],
    queryFn: () =>
      fetchSecretarias({
        municipioId,
        ativo: statusFilter,
        search: searchTerm,
      }),
    staleTime: 30_000,
  })

  const form = useForm<OnboardingInput>({
    resolver: zodResolver(onboardingSchema),
    defaultValues: {
      municipio: '',
      responsavel: '',
      email: '',
      telefone: '',
      modulos: ['educacao'],
      inicio: '7-dias',
    },
  })

  const selectedModules =
    useWatch({
      control: form.control,
      name: 'modulos',
    }) ?? []

  const tiptapEditor = useEditor({
    extensions: [StarterKit],
    content:
      '<h3>Comunicado interno</h3><p>Equipe, iniciamos o onboarding das secretarias com foco em rastreabilidade, indicadores e eficiência operacional.</p>',
  })

  const columns = useMemo<ColumnDef<SecretariaRow>[]>(
    () => [
      {
        accessorKey: 'nome',
        header: 'Secretaria',
        cell: ({ row }) => (
          <div className="flex flex-col">
            <span className="font-semibold text-slate-800">{row.original.nome}</span>
            <span className="text-xs text-slate-500">{row.original.sigla || 'Sem sigla'}</span>
          </div>
        ),
      },
      {
        accessorKey: 'municipio_nome',
        header: 'Município',
      },
      {
        accessorKey: 'tipo_modelo',
        header: 'Modelo',
        cell: ({ row }) => row.original.tipo_modelo || 'GERAL',
      },
      {
        accessorKey: 'apps_ativos',
        header: 'Módulos ativos',
        cell: ({ row }) => row.original.apps_ativos.length,
      },
      {
        accessorKey: 'ativo',
        header: 'Status',
        cell: ({ row }) =>
          row.original.ativo ? (
            <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200">Ativa</Badge>
          ) : (
            <Badge className="bg-rose-50 text-rose-700 border-rose-200">Inativa</Badge>
          ),
      },
    ],
    [],
  )

  const table = useReactTable({
    data: secretariasQuery.data?.results ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: {
        pageSize: 8,
      },
    },
  })

  const barChartData = useMemo(() => {
    const labels = (overviewQuery.data?.top_modulos ?? []).map((item) => item.nome)
    const totals = (overviewQuery.data?.top_modulos ?? []).map((item) => item.total)

    return {
      labels,
      datasets: [
        {
          label: 'Secretarias com módulo ativo',
          data: totals,
          backgroundColor: '#2468d6',
          borderRadius: 8,
        },
      ],
    }
  }, [overviewQuery.data?.top_modulos])

  const contactoHref = montarContatoMailto(payloadPreview)

  return (
    <Tooltip.Provider>
      <div className="min-h-screen bg-[radial-gradient(circle_at_20%_0%,#f1f6ff_0%,#e7effd_30%,#dde7fb_100%)] px-4 pb-8 pt-4 text-slate-700 md:px-8">
        <div className="mx-auto max-w-7xl">
          <Card className="mb-4 border-blue-100 bg-white/85 p-5">
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <div>
                <h1 className="text-2xl font-bold text-slate-900">Frontend profissional do GEPUB</h1>
                <p className="text-sm text-slate-600">
                  React + TypeScript + Tailwind + Radix + Query + Table + Forms + Charts + Tiptap.
                </p>
              </div>
              <Badge>Stack ativa</Badge>
            </div>
          </Card>

          <Tabs.Root defaultValue="visao" className="space-y-4">
            <Tabs.List className="grid grid-cols-2 gap-2 rounded-xl border border-blue-100 bg-white/80 p-1 md:grid-cols-4">
              <Tabs.Trigger className="tab-trigger" value="visao">
                <ChartNoAxesColumn size={16} />
                Visão
              </Tabs.Trigger>
              <Tabs.Trigger className="tab-trigger" value="secretarias">
                <TableIcon size={16} />
                Secretarias
              </Tabs.Trigger>
              <Tabs.Trigger className="tab-trigger" value="onboarding">
                <Settings2 size={16} />
                Onboarding
              </Tabs.Trigger>
              <Tabs.Trigger className="tab-trigger" value="editor">
                <Sparkles size={16} />
                Editor
              </Tabs.Trigger>
            </Tabs.List>

            <Tabs.Content value="visao" className="space-y-4">
              <Card className="p-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900">Indicadores da operação municipal</h2>
                    <p className="text-sm text-slate-500">
                      Dados consolidados do backend com filtros e cache do React Query.
                    </p>
                  </div>

                  <Select.Root value={municipioFilter} onValueChange={setMunicipioFilter}>
                    <Select.Trigger className="inline-flex h-10 min-w-56 items-center justify-between rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700">
                      <Select.Value placeholder="Todos os municípios" />
                      <Select.Icon>
                        <ChevronDown size={16} />
                      </Select.Icon>
                    </Select.Trigger>
                    <Select.Portal>
                      <Select.Content className="z-50 rounded-xl border border-slate-200 bg-white p-1 shadow-lg">
                        <Select.Viewport>
                          <Select.Item value="todos" className="select-item">
                            <Select.ItemText>Todos os municípios</Select.ItemText>
                          </Select.Item>
                          {(overviewQuery.data?.municipios ?? []).map((item) => (
                            <Select.Item key={item.id} value={String(item.id)} className="select-item">
                              <Select.ItemText>{`${item.nome} - ${item.uf}`}</Select.ItemText>
                            </Select.Item>
                          ))}
                        </Select.Viewport>
                      </Select.Content>
                    </Select.Portal>
                  </Select.Root>
                </div>
              </Card>

              {overviewQuery.isLoading ? (
                <Card className="p-6 text-sm text-slate-500">Carregando indicadores...</Card>
              ) : overviewQuery.isError ? (
                <Card className="flex items-center gap-2 p-6 text-sm text-rose-600">
                  <AlertCircle size={16} />
                  Falha ao carregar visão integrada.
                </Card>
              ) : (
                <>
                  <div className="grid gap-3 md:grid-cols-4">
                    {[
                      ['Municípios ativos', overviewQuery.data?.kpis.municipios ?? 0, 'Base territorial habilitada'],
                      ['Secretarias', overviewQuery.data?.kpis.secretarias ?? 0, 'Órgãos com operação no sistema'],
                      ['Unidades', overviewQuery.data?.kpis.unidades ?? 0, 'Escolas, postos e setores vinculados'],
                      ['Módulos ativos', overviewQuery.data?.kpis.modulos ?? 0, 'Aplicações com uso em produção'],
                    ].map(([label, value, hint]) => (
                      <Card key={String(label)} className="p-4">
                        <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
                          <span>{label}</span>
                          <Tooltip.Root>
                            <Tooltip.Trigger asChild>
                              <button className="rounded-full text-slate-400 transition hover:text-slate-600">
                                <Circle size={12} />
                              </button>
                            </Tooltip.Trigger>
                            <Tooltip.Portal>
                              <Tooltip.Content className="max-w-52 rounded-lg bg-slate-900 px-2 py-1 text-xs text-white shadow-md" sideOffset={6}>
                                {hint}
                              </Tooltip.Content>
                            </Tooltip.Portal>
                          </Tooltip.Root>
                        </div>
                        <div className="text-2xl font-bold text-slate-900">{String(value)}</div>
                      </Card>
                    ))}
                  </div>

                  <div className="grid gap-4 lg:grid-cols-2">
                    <Card className="p-4">
                      <h3 className="mb-3 text-sm font-semibold text-slate-800">Evolução mensal de módulos ativos</h3>
                      <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={overviewQuery.data?.timeline ?? []}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                            <XAxis dataKey="mes" tick={{ fill: '#64748b', fontSize: 12 }} />
                            <YAxis allowDecimals={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                            <RechartsTooltip />
                            <Line type="monotone" dataKey="total" stroke="#2468d6" strokeWidth={3} dot={{ r: 3 }} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </Card>

                    <Card className="p-4">
                      <h3 className="mb-3 text-sm font-semibold text-slate-800">Top módulos por secretaria</h3>
                      <div className="h-64">
                        <Bar
                          data={barChartData}
                          options={{
                            maintainAspectRatio: false,
                            plugins: {
                              legend: { display: false },
                            },
                            scales: {
                              x: { ticks: { color: '#64748b' }, grid: { display: false } },
                              y: { ticks: { color: '#64748b' }, grid: { color: '#e2e8f0' } },
                            },
                          }}
                        />
                      </div>
                    </Card>
                  </div>

                  <Card className="p-4">
                    <h3 className="mb-3 text-sm font-semibold text-slate-800">Distribuição por modelo de secretaria</h3>
                    <div className="h-[340px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={overviewQuery.data?.distribuicao_tipos ?? []}
                            dataKey="total"
                            nameKey="nome"
                            innerRadius={70}
                            outerRadius={115}
                            paddingAngle={3}
                          >
                            {(overviewQuery.data?.distribuicao_tipos ?? []).map((item, index) => {
                              const palette = ['#2468d6', '#34a853', '#fbbc05', '#ea4335', '#7e57c2', '#00acc1']
                              return <Cell key={item.nome} fill={palette[index % palette.length]} />
                            })}
                          </Pie>
                          <RechartsTooltip />
                          <RechartsLegend verticalAlign="bottom" height={36} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  </Card>
                </>
              )}
            </Tabs.Content>

            <Tabs.Content value="secretarias" className="space-y-4">
              <Card className="p-4">
                <div className="grid gap-3 md:grid-cols-[1fr,220px]">
                  <label className="relative block">
                    <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                      value={searchTerm}
                      onChange={(event) => setSearchTerm(event.target.value)}
                      className="h-10 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-3 text-sm text-slate-700 outline-none ring-primary/30 transition focus:ring"
                      placeholder="Pesquisar secretaria ou município"
                    />
                  </label>

                  <Select.Root value={statusFilter} onValueChange={(value) => setStatusFilter(value as 'todos' | 'ativos' | 'inativos')}>
                    <Select.Trigger className="inline-flex h-10 items-center justify-between rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700">
                      <Select.Value />
                      <Select.Icon>
                        <ChevronDown size={16} />
                      </Select.Icon>
                    </Select.Trigger>
                    <Select.Portal>
                      <Select.Content className="z-50 rounded-xl border border-slate-200 bg-white p-1 shadow-lg">
                        <Select.Viewport>
                          <Select.Item value="todos" className="select-item">
                            <Select.ItemText>Todos</Select.ItemText>
                          </Select.Item>
                          <Select.Item value="ativos" className="select-item">
                            <Select.ItemText>Apenas ativas</Select.ItemText>
                          </Select.Item>
                          <Select.Item value="inativos" className="select-item">
                            <Select.ItemText>Apenas inativas</Select.ItemText>
                          </Select.Item>
                        </Select.Viewport>
                      </Select.Content>
                    </Select.Portal>
                  </Select.Root>
                </div>
              </Card>

              <Card className="overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead className="bg-slate-50 text-left text-slate-600">
                      {table.getHeaderGroups().map((headerGroup) => (
                        <tr key={headerGroup.id}>
                          {headerGroup.headers.map((header) => (
                            <th key={header.id} className="px-4 py-3 font-semibold">
                              {header.isPlaceholder
                                ? null
                                : flexRender(header.column.columnDef.header, header.getContext())}
                            </th>
                          ))}
                        </tr>
                      ))}
                    </thead>
                    <tbody>
                      {secretariasQuery.isLoading ? (
                        <tr>
                          <td colSpan={columns.length} className="px-4 py-8 text-center text-slate-500">
                            Carregando secretarias...
                          </td>
                        </tr>
                      ) : table.getRowModel().rows.length === 0 ? (
                        <tr>
                          <td colSpan={columns.length} className="px-4 py-8 text-center text-slate-500">
                            Nenhuma secretaria encontrada para os filtros selecionados.
                          </td>
                        </tr>
                      ) : (
                        table.getRowModel().rows.map((row) => (
                          <tr key={row.id} className="border-t border-slate-100">
                            {row.getVisibleCells().map((cell) => (
                              <td key={cell.id} className="px-4 py-3 text-slate-700">
                                {flexRender(cell.column.columnDef.cell, cell.getContext())}
                              </td>
                            ))}
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="flex items-center justify-between border-t border-slate-100 p-3 text-xs text-slate-500">
                  <span>Total carregado: {secretariasQuery.data?.count ?? 0}</span>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => table.previousPage()}
                      disabled={!table.getCanPreviousPage()}
                    >
                      Anterior
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => table.nextPage()}
                      disabled={!table.getCanNextPage()}
                    >
                      Próxima
                    </Button>
                  </div>
                </div>
              </Card>
            </Tabs.Content>

            <Tabs.Content value="onboarding" className="space-y-4">
              <Card className="p-4">
                <h2 className="mb-1 text-lg font-semibold text-slate-900">Onboarding guiado da prefeitura</h2>
                <p className="text-sm text-slate-500">
                  Formulário validado com React Hook Form + Zod e seleção de módulos no estilo app store.
                </p>
              </Card>

              <form className="space-y-4" onSubmit={form.handleSubmit((values) => {
                setPayloadPreview(values)
                setDialogOpen(true)
              })}>
                <Card className="grid gap-3 p-4 md:grid-cols-2">
                  <label className="space-y-1 text-sm">
                    <span className="font-medium text-slate-700">Nome do município</span>
                    <input
                      className="h-10 w-full rounded-xl border border-slate-200 px-3 outline-none ring-primary/30 transition focus:ring"
                      placeholder="Ex.: Santa Aurora"
                      {...form.register('municipio')}
                    />
                    <span className="text-xs text-rose-600">{form.formState.errors.municipio?.message}</span>
                  </label>

                  <label className="space-y-1 text-sm">
                    <span className="font-medium text-slate-700">Responsável</span>
                    <input
                      className="h-10 w-full rounded-xl border border-slate-200 px-3 outline-none ring-primary/30 transition focus:ring"
                      placeholder="Nome e cargo"
                      {...form.register('responsavel')}
                    />
                    <span className="text-xs text-rose-600">{form.formState.errors.responsavel?.message}</span>
                  </label>

                  <label className="space-y-1 text-sm">
                    <span className="font-medium text-slate-700">E-mail institucional</span>
                    <input
                      className="h-10 w-full rounded-xl border border-slate-200 px-3 outline-none ring-primary/30 transition focus:ring"
                      placeholder="contato@prefeitura.gov.br"
                      {...form.register('email')}
                    />
                    <span className="text-xs text-rose-600">{form.formState.errors.email?.message}</span>
                  </label>

                  <label className="space-y-1 text-sm">
                    <span className="font-medium text-slate-700">Telefone</span>
                    <input
                      className="h-10 w-full rounded-xl border border-slate-200 px-3 outline-none ring-primary/30 transition focus:ring"
                      placeholder="(99) 99999-9999"
                      {...form.register('telefone')}
                    />
                    <span className="text-xs text-rose-600">{form.formState.errors.telefone?.message}</span>
                  </label>
                </Card>

                <Card className="p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-slate-800">Configuração dos módulos</h3>
                    <Badge className="bg-slate-100 text-slate-700 border-slate-200">Instalação guiada</Badge>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                    {moduloCatalog.map((module) => {
                      const selected = selectedModules.includes(module.id)
                      return (
                        <button
                          key={module.id}
                          type="button"
                          onClick={() => {
                            const current = form.getValues('modulos')
                            if (current.includes(module.id)) {
                              form.setValue(
                                'modulos',
                                current.filter((item) => item !== module.id),
                                { shouldValidate: true },
                              )
                              return
                            }
                            form.setValue('modulos', [...current, module.id], { shouldValidate: true })
                          }}
                          className={cn(
                            'group rounded-xl border p-4 text-left transition',
                            selected
                              ? 'border-primary bg-blue-50/70 shadow-sm'
                              : 'border-slate-200 bg-white hover:border-blue-300',
                          )}
                        >
                          <div className="mb-3 flex items-center justify-between">
                            <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
                              <Settings2 size={16} />
                            </span>
                            {selected ? <Check size={16} className="text-primary" /> : null}
                          </div>
                          <div className="font-semibold text-slate-900">{module.title}</div>
                          <div className="mt-1 text-xs text-slate-500">{module.description}</div>
                        </button>
                      )
                    })}
                  </div>
                  <p className="mt-2 text-xs text-rose-600">{form.formState.errors.modulos?.message}</p>
                </Card>

                <Card className="p-4">
                  <h3 className="mb-2 text-sm font-semibold text-slate-800">Previsão para início operacional</h3>
                  <div className="grid gap-2 md:grid-cols-3">
                    {[
                      ['imediato', 'Imediato'],
                      ['7-dias', 'Em até 7 dias'],
                      ['15-dias', 'Em até 15 dias'],
                    ].map(([value, label]) => (
                      <label key={value} className="flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm">
                        <input type="radio" value={value} {...form.register('inicio')} />
                        <span>{label}</span>
                      </label>
                    ))}
                  </div>
                </Card>

                <div className="flex justify-end">
                  <Button type="submit" size="lg">
                    Preparar contato comercial
                  </Button>
                </div>
              </form>

              <Dialog.Root open={dialogOpen} onOpenChange={setDialogOpen}>
                <Dialog.Portal>
                  <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-950/50" />
                  <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,560px)] -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white p-5 shadow-2xl">
                    <Dialog.Title className="text-lg font-semibold text-slate-900">Pré-briefing pronto</Dialog.Title>
                    <Dialog.Description className="mt-1 text-sm text-slate-600">
                      Dados estruturados para contato comercial com a equipe GEPUB.
                    </Dialog.Description>

                    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                      <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">
                        {payloadPreview ? JSON.stringify(payloadPreview, null, 2) : '{}'}
                      </pre>
                    </div>

                    <div className="mt-4 flex justify-end gap-2">
                      <Dialog.Close asChild>
                        <Button variant="secondary">Fechar</Button>
                      </Dialog.Close>
                      <a href={contactoHref}>
                        <Button>
                          <Mail size={16} className="mr-2" />
                          Enviar para atendimento
                        </Button>
                      </a>
                    </div>
                  </Dialog.Content>
                </Dialog.Portal>
              </Dialog.Root>
            </Tabs.Content>

            <Tabs.Content value="editor" className="space-y-4">
              <Card className="p-4">
                <h2 className="mb-1 text-lg font-semibold text-slate-900">Comunicados e conteúdo institucional</h2>
                <p className="text-sm text-slate-500">
                  Editor rich-text com Tiptap para notícias, boletins e atualizações do portal.
                </p>
              </Card>

              <Card className="p-4">
                <div className="mb-3 flex flex-wrap gap-2">
                  <Button variant="secondary" size="sm" onClick={() => tiptapEditor?.chain().focus().toggleBold().run()}>
                    Negrito
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => tiptapEditor?.chain().focus().toggleItalic().run()}>
                    Itálico
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => tiptapEditor?.chain().focus().toggleBulletList().run()}>
                    Lista
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => tiptapEditor?.chain().focus().setParagraph().run()}>
                    Parágrafo
                  </Button>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-3">
                  <EditorContent editor={tiptapEditor} className="prose max-w-none prose-slate min-h-40" />
                </div>
              </Card>
            </Tabs.Content>
          </Tabs.Root>
        </div>
      </div>
    </Tooltip.Provider>
  )
}

export default App
