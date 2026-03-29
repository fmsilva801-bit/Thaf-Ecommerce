const state = {
  token: localStorage.getItem("token") || "",
  user: null,
  products: [],
  categories: [],
  selectedProductIds: new Set(),
  selectedCategoryIds: new Set(),
  sales: [],
  selectedSaleIds: new Set(),
  movements: [],
  selectedMovementIds: new Set(),
  financeEntries: [],
  selectedFinanceIds: new Set(),
  users: [],
  selectedUserIds: new Set(),
  suppliers: [],
  selectedSupplierIds: new Set(),
  purchases: [],
  selectedPurchaseIds: new Set(),
  costCalculations: [],
  dashboard: null,
  dashboardFilter: { start: "", end: "", preset: "30d" },
  costDraft: [],
  editingProductId: null,
  editingCategoryId: null,
  editingSaleId: null,
  editingUserId: null,
  editingPurchaseId: null,
  userAvatarDraft: null,
  sidebarCollapsed: localStorage.getItem("sidebarCollapsed") === "1",
  activeSection: "dashboard",
  financeChartModel: null,
  financeHoverIndex: -1,
  salesEndpointAvailable: true,
  authMode: "login",
  authBusy: false,
};

const MODULE_DEFINITIONS = [
  { key: "dashboard", label: "Dashboard", section: "dashboard" },
  { key: "products", label: "Produtos", section: "produtos" },
  { key: "products", label: "Categorias", section: "categorias" },
  { key: "costs", label: "Calculadora de Custos", section: "custos" },
  { key: "purchases", label: "Compras / Fornecedores", section: "compras" },
  { key: "inventory", label: "Estoque", section: "estoque" },
  { key: "sales", label: "Vendas", section: "vendas" },
  { key: "finance", label: "Financeiro", section: "financeiro" },
  { key: "users", label: "Usuarios", section: "usuarios" },
];

const SECTION_TO_MODULE = MODULE_DEFINITIONS.reduce((acc, item) => {
  acc[item.section] = item.key;
  return acc;
}, {});

const sectionMeta = {
  dashboard: { kicker: "Visao Geral", title: "Dashboard Executivo" },
  produtos: { kicker: "Cadastro", title: "Produtos" },
  categorias: { kicker: "Cadastro", title: "Categorias" },
  custos: { kicker: "Precificação", title: "Calculadora de Custos" },
  compras: { kicker: "Suprimentos", title: "Compras e Fornecedores" },
  estoque: { kicker: "Operacao", title: "Controle de Estoque" },
  vendas: { kicker: "Comercial", title: "Lancamento de Vendas" },
  financeiro: { kicker: "Financeiro", title: "Gestao de Entradas e Saidas" },
  usuarios: { kicker: "Administracao", title: "Gestao de Usuarios e Permissoes" },
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const LOGIN_SUBMIT_TEXT = "Entrar na plataforma";
const SIGNUP_SUBMIT_TEXT = "Criar empresa e acessar";
const isMobileViewport = () => window.matchMedia("(max-width: 960px)").matches;

function toDateInputValue(dateObj) {
  const y = dateObj.getFullYear();
  const m = String(dateObj.getMonth() + 1).padStart(2, "0");
  const d = String(dateObj.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function toDateTimeLocalValue(dateObj = new Date()) {
  const y = dateObj.getFullYear();
  const m = String(dateObj.getMonth() + 1).padStart(2, "0");
  const d = String(dateObj.getDate()).padStart(2, "0");
  const hh = String(dateObj.getHours()).padStart(2, "0");
  const mm = String(dateObj.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${d}T${hh}:${mm}`;
}

function setOperationDateDefaults() {
  const nowValue = toDateTimeLocalValue();
  ["#entryDateTime", "#exitDateTime", "#saleDateTime", "#expenseDateTime", "#incomeDateTime", "#purchaseDateTime"].forEach((selector) => {
    const input = $(selector);
    if (input) {
      input.value = nowValue;
    }
  });
}

function formatPeriodDate(dateStr) {
  const d = new Date(`${dateStr}T00:00:00`);
  if (Number.isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString("pt-BR");
}

function setDashboardRange(preset) {
  const now = new Date();
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  let start = new Date(end);
  let endPreset = new Date(end);

  if (preset === "today") {
    start = new Date(end);
  } else if (preset === "7d") {
    start.setDate(start.getDate() - 6);
  } else if (preset === "30d") {
    start.setDate(start.getDate() - 29);
  } else if (preset === "month") {
    start = new Date(end.getFullYear(), end.getMonth(), 1);
  } else if (preset === "last-month") {
    start = new Date(end.getFullYear(), end.getMonth() - 1, 1);
    endPreset = new Date(end.getFullYear(), end.getMonth(), 0);
  }

  state.dashboardFilter.start = toDateInputValue(start);
  state.dashboardFilter.end = toDateInputValue(endPreset);
  state.dashboardFilter.preset = preset;
  $("#dashboardStartDate").value = state.dashboardFilter.start;
  $("#dashboardEndDate").value = state.dashboardFilter.end;

  $$(".range-chip").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.range === preset);
  });
}

function setDashboardCustomRangeFromInputs() {
  const start = $("#dashboardStartDate").value;
  const end = $("#dashboardEndDate").value;
  if (!start || !end) {
    throw new Error("Informe data inicial e data final.");
  }
  if (start > end) {
    throw new Error("A data inicial não pode ser maior que a data final.");
  }
  state.dashboardFilter.start = start;
  state.dashboardFilter.end = end;
  state.dashboardFilter.preset = "custom";
  $$(".range-chip").forEach((btn) => btn.classList.remove("active"));
}

const formatMoney = (v) =>
  Number(v || 0).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });

const formatMoneyShort = (value) => {
  const number = Number(value || 0);
  const abs = Math.abs(number);
  const sign = number < 0 ? "-" : "";
  if (abs >= 1_000_000) return `${sign}R$ ${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${sign}R$ ${(abs / 1_000).toFixed(1)}k`;
  return `${sign}R$ ${abs.toFixed(0)}`;
};

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value || "-";
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function toDateTimeLocalFromIso(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return toDateTimeLocalValue();
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${d}T${hh}:${mm}`;
}

function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function getOperationalProducts({ includeInactiveSelectedId = null } = {}) {
  return state.products.filter((product) => {
    if (Number(product.is_active || 0) === 1) return true;
    if (includeInactiveSelectedId !== null && Number(product.id) === Number(includeInactiveSelectedId)) return true;
    return false;
  });
}

function parsePositiveInteger(value, label) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0 || !Number.isInteger(numeric)) {
    throw new Error(`${label} deve ser um número inteiro maior que zero.`);
  }
  return numeric;
}

function getFilteredMovements() {
  const query = normalizeText($("#movementSearch").value);
  return state.movements.filter((m) => {
    if (!query) return true;
    const movementLabel = m.movement_type === "entry" ? "entrada" : "saida";
    return normalizeText(
      `${m.product_name} ${m.sku || ""} ${m.barcode || ""} ${m.category || ""} ${m.movement_type} ${movementLabel} ${m.note || ""}`
    ).includes(query);
  });
}

function resolveProductByLookupQuery(query, options = {}) {
  const { activeOnly = false } = options;
  const raw = String(query || "").trim();
  if (!raw) return null;
  const normalized = normalizeText(raw);
  const source = activeOnly ? getOperationalProducts() : state.products;
  const exact = source.find((p) => {
    return (
      normalizeText(p.sku || "") === normalized ||
      normalizeText(p.barcode || "") === normalized ||
      normalizeText(p.name || "") === normalized
    );
  });
  if (exact) return exact;
  const matches = source.filter((p) =>
    normalizeText(`${p.name || ""} ${p.sku || ""} ${p.barcode || ""}`).includes(normalized)
  );
  if (matches.length === 1) return matches[0];
  return null;
}

function getFilteredProducts() {
  const query = normalizeText($("#productSearch").value);
  const statusFilter = $("#productStatusFilter")?.value || "all";
  return state.products.filter((p) => {
    if (statusFilter === "active" && !p.is_active) return false;
    if (statusFilter === "inactive" && p.is_active) return false;
    if (!query) return true;
    return normalizeText(`${p.name} ${p.sku || ""} ${p.category || ""} ${p.brand || ""} ${p.barcode || ""}`).includes(query);
  });
}

function getFilteredSales() {
  const query = normalizeText($("#salesSearch")?.value || "");
  return state.sales.filter((sale) => {
    if (!query) return true;
    return normalizeText(
      `${sale.product_name} ${sale.sku || ""} ${sale.barcode || ""} ${sale.category || ""} ${sale.total} ${sale.unit_price} ${sale.qty} ${
        sale.net_profit || 0
      } ${sale.taxes_total || 0} concluida`
    ).includes(query);
  });
}

function getFilteredFinanceEntries() {
  const query = normalizeText($("#financeSearch").value);
  return state.financeEntries.filter((entry) => {
    if (!query) return true;
    const entryLabel = entry.entry_type === "income" ? "ganho entrada" : "gasto saida";
    return normalizeText(`${entry.entry_type} ${entryLabel} ${entry.category} ${entry.description || ""}`).includes(query);
  });
}

function getFilteredUsers() {
  const query = normalizeText($("#usersSearch").value);
  const statusFilter = $("#userStatusFilter")?.value || "all";
  return state.users.filter((user) => {
    if (statusFilter === "active" && !user.is_active) return false;
    if (statusFilter === "inactive" && user.is_active) return false;
    if (!query) return true;
    return normalizeText(`${user.name} ${user.email} ${user.role}`).includes(query);
  });
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function setSelectAllState(inputEl, selectedCount, totalCount) {
  if (!inputEl) return;
  const allChecked = totalCount > 0 && selectedCount === totalCount;
  const partial = selectedCount > 0 && selectedCount < totalCount;
  inputEl.checked = allChecked;
  inputEl.indeterminate = partial;
}

function getUserInitials(name) {
  const parts = String(name || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) return "US";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

function renderAvatarHtml(name, avatarUrl, className = "avatar-circle") {
  const src = String(avatarUrl || "").trim();
  const initials = escapeHtml(getUserInitials(name));
  if (src) {
    return `<span class="${className}"><img src="${escapeHtml(src)}" alt="Avatar de ${escapeHtml(name || "usuário")}" /></span>`;
  }
  return `<span class="${className} avatar-fallback">${initials}</span>`;
}

function renderUserAvatarPreview(name) {
  const preview = $("#userAvatarPreview");
  if (!preview) return;
  preview.innerHTML = renderAvatarHtml(name, state.userAvatarDraft, "avatar-preview-circle");
}

function updateSidebarIdentity() {
  if (!state.user) return;
  const brandMark = $("#brandMark");
  if (brandMark) {
    brandMark.innerHTML = renderAvatarHtml(state.user.name, state.user.avatar_url, "brand-avatar");
  }
  const userInfo = $("#userInfo");
  if (userInfo) {
    const companyPart = state.user.company_name ? ` • ${state.user.company_name}` : "";
    userInfo.textContent = `${state.user.name} (${state.user.role})${companyPart}`;
  }
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Não foi possível ler o arquivo de imagem."));
    reader.readAsDataURL(file);
  });
}

function setFeedback(message, isError = false) {
  const appFeedback = $("#feedback");
  const loginFeedback = $("#loginFeedback");
  const loginVisible = !$("#loginShell").classList.contains("hidden");
  const target = loginVisible ? loginFeedback : appFeedback;

  if (!target) return;
  if (target === loginFeedback) {
    target.classList.remove("success", "error");
    target.classList.add(isError ? "error" : "success");
    target.style.color = "";
  } else {
    target.style.color = isError ? "#2c2f37" : "#545966";
  }
  target.textContent = message;
  if (target === appFeedback) {
    target.style.background = isError ? "#eceff4" : "#f5f7fa";
  }

  if (target === loginFeedback) {
    appFeedback.textContent = "";
    appFeedback.style.background = "transparent";
  } else if (loginFeedback) {
    loginFeedback.textContent = "";
  }

  if (message) {
    const toast = $("#toast");
    if (toast) {
      toast.classList.remove("hidden", "error");
      if (isError) toast.classList.add("error");
      toast.textContent = message;
      window.clearTimeout(setFeedback.toastTimer);
      setFeedback.toastTimer = window.setTimeout(() => {
        toast.classList.add("hidden");
      }, 3200);
    }

    window.clearTimeout(setFeedback.timer);
    setFeedback.timer = window.setTimeout(() => {
      target.textContent = "";
      if (target === loginFeedback) {
        target.classList.remove("success", "error");
      }
      if (target === appFeedback) {
        target.style.background = "transparent";
      }
    }, 3800);
  }
}

function setButtonLoading(button, loading = true, loadingText = "Processando...") {
  if (!button) return () => {};
  const originalText = button.textContent;
  if (loading) {
    button.disabled = true;
    button.classList.add("is-loading");
    button.textContent = loadingText;
  } else {
    button.disabled = false;
    button.classList.remove("is-loading");
    button.textContent = originalText;
  }
  return () => {
    button.disabled = false;
    button.classList.remove("is-loading");
    button.textContent = originalText;
  };
}

function setLoginSubmitState(stateName = "idle") {
  const button = $("#loginSubmitBtn");
  if (!button) return;
  const isSignup = state.authMode === "signup";

  button.classList.remove("is-loading", "is-success", "is-error");

  if (stateName === "loading") {
    button.disabled = true;
    button.classList.add("is-loading");
    button.textContent = isSignup ? "Criando conta..." : "Entrando...";
    return;
  }

  if (stateName === "success") {
    button.disabled = true;
    button.classList.add("is-success");
    button.textContent = isSignup ? "Conta criada" : "Acesso liberado";
    return;
  }

  if (stateName === "error") {
    button.disabled = false;
    button.classList.add("is-error");
    button.textContent = "Tentar novamente";
    return;
  }

  button.disabled = false;
  button.textContent = isSignup ? SIGNUP_SUBMIT_TEXT : LOGIN_SUBMIT_TEXT;
}

function setAuthMode(mode = "login") {
  if (state.authBusy) return;
  const nextMode = mode === "signup" ? "signup" : "login";
  state.authMode = nextMode;

  const signupFields = $("#signupFields");
  const title = $("#loginTitle");
  const subtitle = $("#loginSubtitle");
  const hint = $("#loginHint");
  const emailLabel = $("#authEmailLabel");
  const passwordLabel = $("#authPasswordLabel");
  const emailInput = $("#loginEmail");
  const passwordInput = $("#loginPassword");
  const loginTab = $("#authModeLogin");
  const signupTab = $("#authModeSignup");

  if (signupFields) {
    signupFields.classList.toggle("hidden", nextMode !== "signup");
    signupFields.querySelectorAll("input, select, textarea").forEach((field) => {
      field.disabled = nextMode !== "signup";
    });
  }
  if (title) {
    title.textContent = nextMode === "signup" ? "Criar empresa" : "Entrar";
  }
  if (subtitle) {
    subtitle.textContent =
      nextMode === "signup"
        ? "Cadastre sua empresa e o usuário master inicial."
        : "Acesse seu painel com email e senha.";
  }
  if (hint) {
    hint.classList.toggle("hidden", nextMode === "signup");
  }
  if (emailLabel) {
    emailLabel.textContent = nextMode === "signup" ? "Email do administrador" : "Email";
  }
  if (passwordLabel) {
    passwordLabel.textContent = nextMode === "signup" ? "Senha inicial do administrador" : "Senha";
  }
  if (emailInput) {
    emailInput.placeholder = nextMode === "signup" ? "admin@suaempresa.com" : "usuario@empresa.com";
  }
  if (passwordInput) {
    passwordInput.placeholder = nextMode === "signup" ? "Crie uma senha de acesso" : "Digite sua senha";
  }
  if (loginTab) {
    loginTab.classList.toggle("active", nextMode === "login");
    loginTab.setAttribute("aria-selected", nextMode === "login" ? "true" : "false");
  }
  if (signupTab) {
    signupTab.classList.toggle("active", nextMode === "signup");
    signupTab.setAttribute("aria-selected", nextMode === "signup" ? "true" : "false");
  }
  const loginFeedback = $("#loginFeedback");
  if (loginFeedback) {
    loginFeedback.textContent = "";
    loginFeedback.classList.remove("success", "error");
  }
  setLoginSubmitState("idle");
}

async function api(path, method = "GET", body = null) {
  const headers = { "Content-Type": "application/json" };
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }

  const response = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "Falha na comunicacao com o servidor.");
  }
  return data;
}

async function apiOptional(path, fallbackValue, onError = null) {
  try {
    return await api(path);
  } catch (error) {
    if (typeof onError === "function") {
      onError(error);
    }
    return fallbackValue;
  }
}

function renderCostDraft() {
  const summary = $("#costCalcSummary");
  if (!summary) return;
  const costAmount = Number($("#calcCost")?.value || 0);
  const shippingAmount = Number($("#calcShipping")?.value || 0);
  const otherCostsAmount = Number($("#calcOtherCosts")?.value || 0);
  const taxPercent = Number($("#calcTaxPercent")?.value || 0);
  const commissionPercent = Number($("#calcCommissionPercent")?.value || 0);
  const marginPercent = Number($("#calcMarginPercent")?.value || 0);

  const fixedBase = costAmount + shippingAmount + otherCostsAmount;
  const denominator = 1 - (taxPercent + commissionPercent + marginPercent) / 100;
  const salePrice = denominator > 0 ? fixedBase / denominator : 0;
  const taxAmount = salePrice * (taxPercent / 100);
  const commissionAmount = salePrice * (commissionPercent / 100);
  const profitAmount = salePrice * (marginPercent / 100);

  const calc = {
    cost_amount: Number(costAmount.toFixed(2)),
    shipping_amount: Number(shippingAmount.toFixed(2)),
    other_costs_amount: Number(otherCostsAmount.toFixed(2)),
    tax_percent: Number(taxPercent.toFixed(2)),
    commission_percent: Number(commissionPercent.toFixed(2)),
    margin_percent: Number(marginPercent.toFixed(2)),
    tax_amount: Number(taxAmount.toFixed(2)),
    commission_amount: Number(commissionAmount.toFixed(2)),
    profit_amount: Number(profitAmount.toFixed(2)),
    sale_price: Number(salePrice.toFixed(2)),
  };
  state.currentCostCalc = calc;

  summary.innerHTML = `
    <div class="kpi-grid">
      <article class="metric"><p class="label">Custo do produto</p><p class="value">${formatMoney(calc.cost_amount)}</p></article>
      <article class="metric"><p class="label">Taxa de envio</p><p class="value">${formatMoney(calc.shipping_amount)}</p></article>
      <article class="metric"><p class="label">Outros custos</p><p class="value">${formatMoney(calc.other_costs_amount)}</p></article>
      <article class="metric"><p class="label">Impostos (${calc.tax_percent.toFixed(2)}%)</p><p class="value">${formatMoney(calc.tax_amount)}</p></article>
      <article class="metric"><p class="label">Comissão (${calc.commission_percent.toFixed(2)}%)</p><p class="value">${formatMoney(calc.commission_amount)}</p></article>
      <article class="metric"><p class="label">Lucro (${calc.margin_percent.toFixed(2)}%)</p><p class="value">${formatMoney(calc.profit_amount)}</p></article>
      <article class="metric"><p class="label">Preço de venda</p><p class="value">${calc.sale_price > 0 ? formatMoney(calc.sale_price) : "Reveja percentuais"}</p></article>
    </div>
  `;
}

function renderCostCalculationHistory() {
  const wrap = $("#costCalcHistoryTable");
  if (!wrap) return;
  if (!state.costCalculations.length) {
    wrap.innerHTML = "<div class='empty-state'>Nenhum cálculo salvo até o momento.</div>";
    return;
  }
  wrap.innerHTML = `<table>
    <thead><tr><th>Data</th><th>Produto</th><th>Custo base</th><th>Custos extras</th><th>Impostos</th><th>Comissão</th><th>Lucro</th><th>Preço venda</th><th>Ações</th></tr></thead>
    <tbody>${state.costCalculations
      .map(
        (c) => `<tr>
      <td>${formatDate(c.created_at)}</td>
      <td>${escapeHtml(c.product_name || "Avulso")}</td>
      <td>${formatMoney(c.cost_amount || 0)}</td>
      <td>${formatMoney(Number(c.shipping_amount || 0) + Number(c.other_costs_amount || 0))}</td>
      <td>${formatMoney(c.tax_amount || 0)}</td>
      <td>${formatMoney(c.commission_amount || 0)}</td>
      <td>${formatMoney(c.profit_amount || 0)}</td>
      <td>${formatMoney(c.sale_price || 0)}</td>
      <td><button class="btn-inline delete" data-delete-cost-calc="${c.id}">Excluir</button></td>
    </tr>`
      )
      .join("")}</tbody>
  </table>`;
  $$("[data-delete-cost-calc]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.deleteCostCalc);
      if (!window.confirm("Deseja excluir este cálculo salvo?")) return;
      try {
        await api(`/api/cost-calculations/${id}`, "DELETE");
        await refreshCore();
        setFeedback("Cálculo excluído com sucesso.");
      } catch (error) {
        setFeedback(error.message, true);
      }
    });
  });
}

function resetProductFormMode() {
  state.editingProductId = null;
  $("#productForm").reset();
  $("#productStatus").value = "active";
  $("#productUnit").value = "un";
  $("#productCost").value = "0";
  $("#productFormTitle").textContent = "Cadastro de produto";
  $("#saveProductBtn").textContent = "Salvar produto";
  $("#productModeBadge").textContent = "Modo criacao";
  $("#productModeBadge").classList.remove("mode-edit");
  $("#cancelEditBtn").classList.add("hidden");
}

function setProductEditMode(product) {
  state.editingProductId = Number(product.id);
  renderCategorySelect(product.category_id ? Number(product.category_id) : null);
  $("#sku").value = product.sku || "";
  $("#productName").value = product.name || "";
  $("#productCategory").value = product.category_id ? String(product.category_id) : "";
  $("#productDescription").value = product.description || "";
  $("#productStatus").value = product.is_active ? "active" : "inactive";
  $("#productBrand").value = product.brand || "";
  $("#productUnit").value = product.unit || "un";
  $("#productCost").value = String(Number(product.cost_price || 0));
  $("#productBarcode").value = product.barcode || "";
  $("#productFormTitle").textContent = `Editando produto: ${product.name}`;
  $("#saveProductBtn").textContent = "Atualizar produto";
  $("#productModeBadge").textContent = "Modo edicao";
  $("#productModeBadge").classList.add("mode-edit");
  $("#cancelEditBtn").classList.remove("hidden");
  $("#produtosSection").scrollIntoView({ behavior: "smooth", block: "start" });
}

function resetSaleFormMode() {
  state.editingSaleId = null;
  $("#saleForm").reset();
  if ($("#saleProductQuery")) $("#saleProductQuery").value = "";
  $("#saleQty").value = "1";
  $("#saleDateTime").value = toDateTimeLocalValue();
  $("#saleFormTitle").textContent = "Lancamento de vendas";
  $("#saveSaleBtn").textContent = "Registrar venda";
  $("#saleModeBadge").textContent = "Modo criacao";
  $("#cancelSaleEditBtn").classList.add("hidden");
}

function setSaleEditMode(sale) {
  state.editingSaleId = Number(sale.id);
  $("#saleProduct").value = String(sale.product_id || "");
  if ($("#saleProductQuery")) {
    $("#saleProductQuery").value = sale.product_name || "";
  }
  $("#saleQty").value = String(Number(sale.qty || 1));
  $("#salePrice").value = String(Number(sale.unit_price || 0));
  const rawDate = String(sale.created_at || "");
  $("#saleDateTime").value = rawDate ? rawDate.slice(0, 16) : toDateTimeLocalValue();
  $("#saleFormTitle").textContent = `Editando venda #${sale.id}`;
  $("#saveSaleBtn").textContent = "Salvar edicao";
  $("#saleModeBadge").textContent = "Modo edicao";
  $("#cancelSaleEditBtn").classList.remove("hidden");
  $("#vendasSection").scrollIntoView({ behavior: "smooth", block: "start" });
}

function resetPurchaseFormMode() {
  state.editingPurchaseId = null;
  $("#purchaseForm").reset();
  $("#purchaseType").value = "inventory";
  $("#purchaseProduct").disabled = false;
  $("#purchaseProduct").value = "";
  $("#purchaseQty").value = "1";
  $("#purchaseUnitCost").value = "0";
  $("#purchasePaymentMethod").value = "PIX";
  $("#purchasePaymentTerms").value = "À vista";
  $("#purchasePaymentStatus").value = "pendente";
  $("#purchaseDateTime").value = toDateTimeLocalValue();
  $("#savePurchaseBtn").textContent = "Registrar compra";
  $("#cancelPurchaseEditBtn").classList.add("hidden");
}

function setPurchaseEditMode(purchase) {
  state.editingPurchaseId = Number(purchase.id);
  const item = Array.isArray(purchase.items) && purchase.items.length ? purchase.items[0] : null;
  $("#purchaseSupplier").value = purchase.supplier_id ? String(purchase.supplier_id) : "";
  $("#purchaseType").value = purchase.purchase_type || "inventory";
  $("#purchaseDateTime").value = toDateTimeLocalFromIso(purchase.created_at);
  $("#purchaseProduct").value = item?.product_id ? String(item.product_id) : "";
  $("#purchaseItemLabel").value = item?.label || "";
  $("#purchaseQty").value = String(Number(item?.qty || 1));
  $("#purchaseUnitCost").value = String(Number(item?.unit_cost || 0));
  $("#purchasePaymentMethod").value = purchase.payment_method || "PIX";
  $("#purchasePaymentTerms").value = purchase.payment_terms || "À vista";
  $("#purchasePaymentStatus").value = purchase.status || "pendente";
  $("#purchaseNotes").value = purchase.notes || "";
  $("#purchaseProduct").disabled = $("#purchaseType").value !== "inventory";
  $("#savePurchaseBtn").textContent = "Salvar edição";
  $("#cancelPurchaseEditBtn").classList.remove("hidden");
  $("#comprasSection").scrollIntoView({ behavior: "smooth", block: "start" });
}

function loadCostProfileFromProduct(productId) {
  const product = state.products.find((p) => Number(p.id) === Number(productId));
  if (!product) return;
  $("#calcCost").value = String(Number(product.cost_price || 0));
  renderCostDraft();
}

function getUserModulePermissions() {
  if (!state.user) return [];
  const uniqueKeys = Array.from(new Set(MODULE_DEFINITIONS.map((item) => item.key)));
  if (state.user.role === "master") {
    return uniqueKeys;
  }
  const list = Array.isArray(state.user.module_permissions) ? state.user.module_permissions : [];
  return uniqueKeys.filter((key) => list.includes(key));
}

function canAccessModule(moduleKey) {
  if (!moduleKey) return true;
  if (!state.user) return false;
  if (state.user.role === "master") return true;
  return getUserModulePermissions().includes(moduleKey);
}

function allowedSections() {
  return MODULE_DEFINITIONS.filter((item) => canAccessModule(item.key)).map((item) => item.section);
}

function applyNavigationPermissions() {
  MODULE_DEFINITIONS.forEach((item) => {
    const nav = $(`.nav-item[data-section="${item.section}"]`);
    if (!nav) return;
    const mustHideUsers = item.section === "usuarios" && state.user?.role !== "master";
    nav.classList.toggle("hidden", mustHideUsers || !canAccessModule(item.key));
  });
}

function selectedUserPermissionsFromForm() {
  return $$('input[name="userModulePermission"]:checked')
    .map((el) => el.value)
    .filter((value) => MODULE_DEFINITIONS.some((item) => item.key === value));
}

function setUserPermissionsForm(permissions = []) {
  const selected = new Set(Array.isArray(permissions) ? permissions : []);
  $$('input[name="userModulePermission"]').forEach((el) => {
    el.checked = selected.has(el.value);
  });
}

function applyRolePresetToPermissionForm(role) {
  const uniqueKeys = Array.from(new Set(MODULE_DEFINITIONS.map((item) => item.key)));
  if (role === "master") {
    setUserPermissionsForm(uniqueKeys);
    return;
  }
  if (role === "admin") {
    setUserPermissionsForm(MODULE_DEFINITIONS.filter((item) => item.key !== "users").map((item) => item.key));
    return;
  }
  setUserPermissionsForm(["dashboard"]);
}

function applyPermissionPreset(preset) {
  const presets = {
    master: ["dashboard", "products", "costs", "purchases", "inventory", "sales", "finance", "users"],
    admin: ["dashboard", "products", "costs", "purchases", "inventory", "sales", "finance"],
    estoque: ["dashboard", "products", "inventory", "purchases"],
    comercial: ["dashboard", "products", "sales", "costs"],
    financeiro: ["dashboard", "finance", "purchases", "sales"],
  };
  if (!preset || !presets[preset]) return;
  setUserPermissionsForm(presets[preset]);
}

function resetUserFormMode() {
  state.editingUserId = null;
  state.userAvatarDraft = null;
  $("#userForm").reset();
  $("#newUserRole").value = "member";
  applyRolePresetToPermissionForm("member");
  $("#newUserPassword").required = true;
  $("#newUserEmail").disabled = false;
  $("#newUserPassword").placeholder = "";
  if ($("#newUserAvatarFile")) $("#newUserAvatarFile").value = "";
  $("#saveUserBtn").textContent = "Criar usuario";
  $("#userFormTitle").textContent = "Novo usuário";
  $("#cancelUserEditBtn").classList.add("hidden");
  renderUserAvatarPreview($("#newUserName").value || "Novo usuário");
}

function setUserEditMode(row) {
  state.editingUserId = Number(row.id);
  state.userAvatarDraft = row.avatar_url || null;
  $("#newUserName").value = row.name || "";
  $("#newUserEmail").value = row.email || "";
  $("#newUserEmail").disabled = true;
  $("#newUserRole").value = row.role || "member";
  setUserPermissionsForm(row.module_permissions || []);
  $("#newUserPassword").value = "";
  $("#newUserPassword").required = false;
  $("#newUserPassword").placeholder = "Opcional para edicao";
  if ($("#newUserAvatarFile")) $("#newUserAvatarFile").value = "";
  $("#saveUserBtn").textContent = "Salvar alterações";
  $("#userFormTitle").textContent = `Editando: ${row.name}`;
  $("#cancelUserEditBtn").classList.remove("hidden");
  renderUserAvatarPreview(row.name || "Usuário");
  $("#usuariosSection").scrollIntoView({ behavior: "smooth", block: "start" });
}

function applyProductsPermissions() {
  const canManageProducts = canAccessModule("products");
  const canManageCosts = canAccessModule("costs");
  const formInputs = $$("#productForm input, #productForm select");
  const categoryInputs = $$("#categoryForm input, #categoryForm select");
  const costInputs = $$("#costCalculatorForm input, #costCalculatorForm select");
  formInputs.forEach((el) => {
    el.disabled = !canManageProducts;
  });
  categoryInputs.forEach((el) => {
    el.disabled = !canManageProducts;
  });
  costInputs.forEach((el) => {
    el.disabled = !canManageCosts;
  });
  if ($("#saveCostCalcBtn")) $("#saveCostCalcBtn").disabled = !canManageCosts;
  if ($("#clearCostCalcBtn")) $("#clearCostCalcBtn").disabled = !canManageCosts;
  if ($("#saveProductBtn")) $("#saveProductBtn").disabled = !canManageProducts;
  if ($("#saveCategoryBtn")) $("#saveCategoryBtn").disabled = !canManageProducts;
  if (!canManageProducts) {
    $("#cancelEditBtn").classList.add("hidden");
    $("#productModeBadge").textContent = "Modo visualizacao";
    $("#productModeBadge").classList.remove("mode-edit");
  }
}

function applyTopbarFilterVisibility(section) {
  const filters = $("#topbarDateFilters");
  if (!filters) return;
  const visible = section === "dashboard" || section === "financeiro";
  filters.classList.toggle("hidden", !visible);
}

function applySection(section) {
  const moduleKey = SECTION_TO_MODULE[section];
  if (moduleKey && !canAccessModule(moduleKey)) {
    const allowed = allowedSections();
    const fallback = allowed[0] || null;
    if (!fallback) {
      state.activeSection = "";
      Object.keys(sectionMeta).forEach((key) => {
        const sectionEl = $(`#${key}Section`);
        if (sectionEl) sectionEl.classList.add("hidden");
      });
      $$(".nav-item[data-section]").forEach((btn) => btn.classList.remove("active"));
      $("#pageKicker").textContent = "Acesso";
      $("#pageTitle").textContent = "Módulos não autorizados";
      setFeedback("Você não tem permissão para acessar este módulo.", true);
      return;
    }
    if (fallback !== section) {
      setFeedback("Você não tem permissão para acessar este módulo.", true);
      return applySection(fallback);
    }
    setFeedback("Você não tem permissão para acessar este módulo.", true);
    return;
  }

  state.activeSection = section;
  Object.keys(sectionMeta).forEach((key) => {
    $(`#${key}Section`).classList.toggle("hidden", key !== section);
  });

  $$(".nav-item[data-section]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.section === section);
  });

  const meta = sectionMeta[section];
  $("#pageKicker").textContent = meta.kicker;
  $("#pageTitle").textContent = meta.title;
  if ((section === "dashboard" || section === "financeiro") && state.dashboard?.period) {
    $("#pageKicker").textContent = `Periodo ${formatPeriodDate(state.dashboard.period.start)} - ${formatPeriodDate(
      state.dashboard.period.end
    )}`;
  }

  if (section !== "dashboard") {
    hideFinanceTooltip();
    state.financeHoverIndex = -1;
  }

  applyTopbarFilterVisibility(section);
  $("#appShell").classList.remove("menu-open");
}

function applySidebarState() {
  const appShell = $("#appShell");
  const toggle = $("#sidebarToggle");
  if (!appShell || !toggle) return;

  const collapsedDesktop = state.sidebarCollapsed && !isMobileViewport();
  appShell.classList.toggle("sidebar-collapsed", collapsedDesktop);
  toggle.classList.toggle("is-collapsed", collapsedDesktop);
  toggle.setAttribute("aria-label", collapsedDesktop ? "Expandir menu" : "Recolher menu");
}

function showLoginShell() {
  $("#landingShell").classList.add("hidden");
  $("#loginShell").classList.remove("hidden");
  $("#appShell").classList.add("hidden");
  setAuthMode("login");
}

function showLandingShell() {
  $("#landingShell").classList.remove("hidden");
  $("#loginShell").classList.add("hidden");
  $("#appShell").classList.add("hidden");
  setAuthMode("login");
}

function openAuthShell(mode = "login") {
  $("#landingShell").classList.add("hidden");
  $("#loginShell").classList.remove("hidden");
  $("#appShell").classList.add("hidden");
  setAuthMode(mode);
}

function showAppShell() {
  $("#landingShell").classList.add("hidden");
  $("#loginShell").classList.add("hidden");
  $("#appShell").classList.remove("hidden");
}

function renderProductSelects() {
  const activeProducts = getOperationalProducts();
  const productOptions = activeProducts
    .map((product) => `<option value="${product.id}">${escapeHtml(product.name)}${product.sku ? ` • SKU ${escapeHtml(product.sku)}` : ""}</option>`)
    .join("");

  const placeholders = {
    "#entryProduct": "Selecione um produto",
    "#exitProduct": "Selecione um produto",
    "#saleProduct": "Selecione um produto",
    "#purchaseProduct": "Selecione um produto (opcional)",
  };

  ["#entryProduct", "#exitProduct", "#saleProduct", "#purchaseProduct"].forEach((selector) => {
    const el = $(selector);
    if (!el) return;
    const previousValue = el.value;
    el.innerHTML = `<option value="">${placeholders[selector] || "Selecione"}</option>${productOptions}`;
    if (previousValue && activeProducts.some((product) => String(product.id) === String(previousValue))) {
      el.value = previousValue;
    }
  });

  const costCalcProduct = $("#costCalcProduct");
  if (costCalcProduct) {
    costCalcProduct.innerHTML = `<option value="">Simulação avulsa (manual)</option>${productOptions}`;
  }

  const datalist = $("#productsLookupList");
  if (datalist) {
    const options = [];
    activeProducts.forEach((product) => {
      const name = escapeHtml(product.name || "");
      const sku = escapeHtml(product.sku || "");
      const barcode = escapeHtml(product.barcode || "");
      options.push(`<option value="${name}">${sku || "-"} | ${barcode || "-"}</option>`);
      if (sku) options.push(`<option value="${sku}">${name} | SKU</option>`);
      if (barcode) options.push(`<option value="${barcode}">${name} | Código de barras</option>`);
    });
    datalist.innerHTML = options.join("");
  }
}

function renderSupplierSelect() {
  const options = [`<option value="">Sem fornecedor</option>`]
    .concat(
      state.suppliers
        .filter((s) => Number(s.is_active || 0) === 1)
        .map((s) => `<option value="${s.id}">${escapeHtml(s.name)}</option>`)
    )
    .join("");
  const el = $("#purchaseSupplier");
  if (el) el.innerHTML = options;
}

function renderCategorySelect(includeInactiveId = null) {
  const select = $("#productCategory");
  if (!select) return;
  const options = [`<option value="">Sem categoria</option>`]
    .concat(
      state.categories
        .filter((c) => Number(c.is_active || 0) === 1 || (includeInactiveId && Number(c.id) === includeInactiveId))
        .map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`)
    )
    .join("");
  select.innerHTML = options;
}

function resetCategoryFormMode() {
  state.editingCategoryId = null;
  $("#categoryForm").reset();
  $("#categoryStatus").value = "active";
  $("#categoryFormTitle").textContent = "Cadastro de categorias";
  $("#saveCategoryBtn").textContent = "Salvar categoria";
  $("#cancelCategoryEditBtn").classList.add("hidden");
}

function setCategoryEditMode(row) {
  state.editingCategoryId = Number(row.id);
  $("#categoryName").value = row.name || "";
  $("#categoryDescription").value = row.description || "";
  $("#categoryStatus").value = Number(row.is_active || 0) === 1 ? "active" : "inactive";
  $("#categoryFormTitle").textContent = `Editando categoria: ${row.name}`;
  $("#saveCategoryBtn").textContent = "Salvar alterações";
  $("#cancelCategoryEditBtn").classList.remove("hidden");
  $("#categoriasSection").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderProducts() {
  const canManage = canAccessModule("products");
  const filtered = getFilteredProducts();
  const visibleIds = new Set(filtered.map((item) => Number(item.id)));
  state.selectedProductIds.forEach((id) => {
    if (!visibleIds.has(Number(id))) {
      state.selectedProductIds.delete(id);
    }
  });

  const deleteSelectedBtn = $("#deleteSelectedProductsBtn");
  const deactivateSelectedBtn = $("#deactivateSelectedProductsBtn");
  if (deleteSelectedBtn) {
    deleteSelectedBtn.disabled = !canManage || state.selectedProductIds.size === 0;
    deleteSelectedBtn.textContent =
      state.selectedProductIds.size > 0 ? `Excluir selecionados (${state.selectedProductIds.size})` : "Excluir selecionados";
  }
  if (deactivateSelectedBtn) {
    deactivateSelectedBtn.disabled = !canManage || state.selectedProductIds.size === 0;
    deactivateSelectedBtn.textContent =
      state.selectedProductIds.size > 0
        ? `Inativar selecionados (${state.selectedProductIds.size})`
        : "Inativar selecionados";
  }

  const wrap = $("#productsTableWrap");
  if (!filtered.length) {
    wrap.innerHTML = "<div class='empty-state'>Nenhum produto encontrado para este filtro.</div>";
    return;
  }

  wrap.innerHTML = `<table>
    <thead>
      <tr>
        ${canManage ? "<th><input type='checkbox' id='selectAllProducts' /></th>" : ""}
        <th>SKU</th>
        <th>Produto</th>
        <th>Categoria</th>
        <th>Marca</th>
        <th>Un.</th>
        <th>Status</th>
        <th>Custo item</th>
        <th>Cód. barras</th>
        <th>Estoque</th>
        <th>Criado em</th>
        ${canManage ? "<th>Acoes</th>" : ""}
      </tr>
    </thead>
    <tbody>${filtered
      .map(
        (p) => `<tr class="${state.selectedProductIds.has(Number(p.id)) ? "is-selected" : ""}">
        ${
          canManage
            ? `<td><input type="checkbox" class="product-check" data-product-check="${p.id}" ${
                state.selectedProductIds.has(Number(p.id)) ? "checked" : ""
              } /></td>`
            : ""
        }
        <td>${escapeHtml(p.sku || "-")}</td>
        <td>${escapeHtml(p.name)}</td>
        <td>${escapeHtml(p.category || "-")}</td>
        <td>${escapeHtml(p.brand || "-")}</td>
        <td>${escapeHtml(p.unit || "un")}</td>
        <td><span class="badge">${p.is_active ? "Ativo" : "Inativo"}</span></td>
        <td>${formatMoney(p.cost_price)}</td>
        <td>${escapeHtml(p.barcode || "-")}</td>
        <td>${p.stock_qty}</td>
        <td>${formatDate(p.created_at)}</td>
        ${canManage ? `<td>
          <div class=\"table-actions\">
            <button class=\"btn-inline edit\" data-edit-product=\"${p.id}\">Editar</button>
            <button class=\"btn-inline delete\" data-delete-product=\"${p.id}\">${p.is_active ? "Excluir" : "Inativado"}</button>
          </div>
        </td>` : ""}
      </tr>`
      )
      .join("")}</tbody>
  </table>`;

  if (!canManage) {
    return;
  }

  const selectAll = $("#selectAllProducts");
  if (selectAll) {
    const selectedVisible = filtered.filter((row) => state.selectedProductIds.has(Number(row.id))).length;
    setSelectAllState(selectAll, selectedVisible, filtered.length);
    selectAll.addEventListener("change", () => {
      if (selectAll.checked) {
        filtered.forEach((row) => state.selectedProductIds.add(Number(row.id)));
      } else {
        filtered.forEach((row) => state.selectedProductIds.delete(Number(row.id)));
      }
      renderProducts();
    });
  }

  $$(".product-check").forEach((check) => {
    check.addEventListener("change", () => {
      const productId = Number(check.dataset.productCheck);
      if (Number.isNaN(productId)) return;
      if (check.checked) {
        state.selectedProductIds.add(productId);
      } else {
        state.selectedProductIds.delete(productId);
      }
      renderProducts();
    });
  });

  $$("[data-edit-product]").forEach((button) => {
    button.addEventListener("click", () => {
      const productId = Number(button.dataset.editProduct);
      const product = state.products.find((item) => Number(item.id) === productId);
      if (!product) return;
      setProductEditMode(product);
      setFeedback(`Produto ${product.name} carregado para edicao.`);
    });
  });

  $$("[data-delete-product]").forEach((button) => {
    button.addEventListener("click", async () => {
      const productId = Number(button.dataset.deleteProduct);
      const product = state.products.find((item) => Number(item.id) === productId);
      if (!product) return;
      if (!product.is_active) {
        setFeedback(`Produto ${product.name} já está inativo.`);
        return;
      }

      const confirmed = window.confirm(`Deseja realmente excluir o produto \"${product.name}\"?`);
      if (!confirmed) return;

      try {
        const result = await api(`/api/products/${productId}`, "DELETE");
        state.selectedProductIds.delete(productId);
        if (result.mode === "deactivated") {
          const target = state.products.find((item) => Number(item.id) === productId);
          if (target) target.is_active = false;
        } else {
          state.products = state.products.filter((item) => Number(item.id) !== productId);
        }
        renderProducts();
        if (state.editingProductId === productId) {
          resetProductFormMode();
        }
        await refreshCore();
        if (result.mode === "deactivated") {
          setFeedback(`Produto ${product.name} inativado para preservar historico.`);
          return;
        }
        setFeedback(`Produto ${product.name} excluido com sucesso.`);
      } catch (error) {
        setFeedback(error.message, true);
      }
    });
  });
}

function renderMovements() {
  const canManage = canAccessModule("inventory");
  const filtered = getFilteredMovements();
  const visibleIds = new Set(filtered.map((item) => Number(item.id)));
  state.selectedMovementIds.forEach((id) => {
    if (!visibleIds.has(Number(id))) {
      state.selectedMovementIds.delete(id);
    }
  });

  const deleteSelectedBtn = $("#deleteSelectedMovementsBtn");
  if (deleteSelectedBtn) {
    deleteSelectedBtn.disabled = !canManage || state.selectedMovementIds.size === 0;
    deleteSelectedBtn.textContent =
      state.selectedMovementIds.size > 0
        ? `Excluir selecionados (${state.selectedMovementIds.size})`
        : "Excluir selecionados";
  }

  $("#movementsTable").innerHTML = filtered.length
    ? `<table>
      <thead><tr>${canManage ? "<th><input type='checkbox' id='selectAllMovements' /></th>" : ""}<th>Data</th><th>Produto</th><th>SKU</th><th>Cód. barras</th><th>Categoria</th><th>Tipo</th><th>Qtd</th><th>Custo un.</th><th>Valor mov.</th><th>Observacao</th>${canManage ? "<th>Acoes</th>" : ""}</tr></thead>
      <tbody>${filtered
        .map(
          (row) => {
            const movementLabel = row.movement_type === "entry" ? "Entrada" : "Saida";
            const movementValue = Number(row.qty || 0) * Number(row.cost_price || 0);
            return `<tr class="${state.selectedMovementIds.has(Number(row.id)) ? "is-selected" : ""}">
            ${
              canManage
                ? `<td><input type="checkbox" class="movement-check" data-movement-check="${row.id}" ${
                    state.selectedMovementIds.has(Number(row.id)) ? "checked" : ""
                  } /></td>`
                : ""
            }
            <td>${formatDate(row.created_at)}</td>
            <td>${escapeHtml(row.product_name)}</td>
            <td>${escapeHtml(row.sku || "-")}</td>
            <td>${escapeHtml(row.barcode || "-")}</td>
            <td>${escapeHtml(row.category || "-")}</td>
            <td><span class="badge ${row.movement_type}">${movementLabel}</span></td>
            <td>${row.qty}</td>
            <td>${formatMoney(row.cost_price || 0)}</td>
            <td>${formatMoney(movementValue)}</td>
            <td>${escapeHtml(row.note || "-")}</td>
            ${
              canManage
                ? `<td>
              <div class="table-actions">
                <button class="btn-inline delete" data-delete-movement="${row.id}">Excluir</button>
              </div>
            </td>`
                : ""
            }
          </tr>`;
          }
        )
        .join("")}</tbody>
    </table>`
    : "<div class='empty-state'>Nenhuma movimentacao encontrada.</div>";

  if (!canManage || !filtered.length) return;

  const selectAll = $("#selectAllMovements");
  if (selectAll) {
    const selectedVisible = filtered.filter((row) => state.selectedMovementIds.has(Number(row.id))).length;
    setSelectAllState(selectAll, selectedVisible, filtered.length);
    selectAll.addEventListener("change", () => {
      if (selectAll.checked) {
        filtered.forEach((row) => state.selectedMovementIds.add(Number(row.id)));
      } else {
        filtered.forEach((row) => state.selectedMovementIds.delete(Number(row.id)));
      }
      renderMovements();
    });
  }

  $$(".movement-check").forEach((check) => {
    check.addEventListener("change", () => {
      const movementId = Number(check.dataset.movementCheck);
      if (Number.isNaN(movementId)) return;
      if (check.checked) {
        state.selectedMovementIds.add(movementId);
      } else {
        state.selectedMovementIds.delete(movementId);
      }
      renderMovements();
    });
  });

  $$("[data-delete-movement]").forEach((button) => {
    button.addEventListener("click", async () => {
      const movementId = Number(button.dataset.deleteMovement);
      const movement = state.movements.find((item) => Number(item.id) === movementId);
      if (!movement) return;

      const movementType = movement.movement_type === "entry" ? "entrada" : "saida";
      const confirmed = window.confirm(
        `Deseja realmente excluir esta movimentacao de ${movementType} (${movement.qty} un) do produto "${movement.product_name}"?`
      );
      if (!confirmed) return;

      try {
        let result;
        try {
          result = await api(`/api/inventory/movements/${movementId}`, "DELETE");
        } catch (error) {
          const canForce = String(error.message || "").toLowerCase().includes("ficaria negativo");
          if (!canForce) {
            throw error;
          }
          const forceConfirm = window.confirm(
            "Esta exclusao deixara o estoque negativo. Deseja excluir mesmo assim?"
          );
          if (!forceConfirm) return;
          result = await api(`/api/inventory/movements/${movementId}?force=1`, "DELETE");
        }
        await refreshCore();
        state.selectedMovementIds.delete(movementId);
        if (result.mode === "sale_deleted") {
          setFeedback("Venda vinculada excluida com sucesso. Estoque e financeiro foram recalculados.");
          return;
        }
        if (result.mode === "forced_negative_stock") {
          setFeedback("Movimentacao excluida com forca. Estoque pode ter ficado negativo.");
          return;
        }
        setFeedback("Movimentacao excluida e estoque recalculado.");
      } catch (error) {
        setFeedback(error.message, true);
        window.alert(error.message);
      }
    });
  });
}

async function deleteSelectedMovements() {
  const stopLoading = setButtonLoading($("#deleteSelectedMovementsBtn"), true, "Excluindo...");
  const ids = Array.from(state.selectedMovementIds);
  if (!ids.length) {
    stopLoading();
    setFeedback("Selecione ao menos uma movimentacao para excluir.", true);
    return;
  }

  const confirmed = window.confirm(`Deseja excluir ${ids.length} movimentacao(oes) selecionada(s)?`);
  if (!confirmed) {
    stopLoading();
    return;
  }

  let deleted = 0;
  let forced = 0;
  let saleDeleted = 0;
  let failed = 0;
  const forceCandidates = [];

  for (const movementId of ids) {
    try {
      const result = await api(`/api/inventory/movements/${movementId}`, "DELETE");
      deleted += 1;
      if (result.mode === "forced_negative_stock") forced += 1;
      if (result.mode === "sale_deleted") saleDeleted += 1;
    } catch (error) {
      const canForce = String(error.message || "").toLowerCase().includes("ficaria negativo");
      if (canForce) {
        forceCandidates.push(movementId);
        continue;
      }
      failed += 1;
    }
  }

  if (forceCandidates.length > 0) {
    const forceConfirm = window.confirm(
      `${forceCandidates.length} movimentação(ões) deixariam estoque negativo. Deseja forçar a exclusão mesmo assim?`
    );
    if (forceConfirm) {
      for (const movementId of forceCandidates) {
        try {
          const forceResult = await api(`/api/inventory/movements/${movementId}?force=1`, "DELETE");
          deleted += 1;
          if (forceResult.mode === "forced_negative_stock") forced += 1;
          if (forceResult.mode === "sale_deleted") saleDeleted += 1;
        } catch {
          failed += 1;
        }
      }
    } else {
      failed += forceCandidates.length;
    }
  }

  state.selectedMovementIds.clear();
  await refreshCore();
  const msg = `Exclusao concluida: ${deleted} removida(s), ${saleDeleted} venda(s) vinculada(s), ${forced} forcada(s), ${failed} falha(s).`;
  setFeedback(msg, failed > 0);
  stopLoading();
}

async function deleteSelectedProducts() {
  const stopLoading = setButtonLoading($("#deleteSelectedProductsBtn"), true, "Excluindo...");
  const ids = Array.from(state.selectedProductIds);
  if (!ids.length) {
    stopLoading();
    setFeedback("Selecione ao menos um produto.", true);
    return;
  }
  const confirmed = window.confirm(`Deseja excluir ${ids.length} produto(s) selecionado(s)?`);
  if (!confirmed) {
    stopLoading();
    return;
  }

  let deleted = 0;
  let deactivated = 0;
  let failed = 0;
  for (const productId of ids) {
    try {
      const result = await api(`/api/products/${productId}`, "DELETE");
      if (result.mode === "deactivated") {
        deactivated += 1;
      } else {
        deleted += 1;
      }
    } catch {
      failed += 1;
    }
  }
  state.selectedProductIds.clear();
  renderProducts();
  await refreshCore();
  setFeedback(`Produtos processados: ${deleted} excluido(s), ${deactivated} inativado(s), ${failed} falha(s).`, failed > 0);
  stopLoading();
}

async function deactivateSelectedProducts() {
  const stopLoading = setButtonLoading($("#deactivateSelectedProductsBtn"), true, "Inativando...");
  const ids = Array.from(state.selectedProductIds);
  if (!ids.length) {
    stopLoading();
    setFeedback("Selecione ao menos um produto.", true);
    return;
  }
  const confirmed = window.confirm(`Deseja inativar ${ids.length} produto(s) selecionado(s)?`);
  if (!confirmed) {
    stopLoading();
    return;
  }

  let deactivated = 0;
  let failed = 0;
  for (const productId of ids) {
    try {
      await api(`/api/products/${productId}/deactivate`, "PUT", {});
      deactivated += 1;
    } catch {
      failed += 1;
    }
  }
  state.selectedProductIds.clear();
  renderProducts();
  await refreshCore();
  setFeedback(`Produtos inativados: ${deactivated}. Falhas: ${failed}.`, failed > 0);
  stopLoading();
}

async function deleteSelectedSales() {
  const stopLoading = setButtonLoading($("#deleteSelectedSalesBtn"), true, "Excluindo...");
  const ids = Array.from(state.selectedSaleIds);
  if (!ids.length) {
    stopLoading();
    setFeedback("Selecione ao menos uma venda.", true);
    return;
  }
  const confirmed = window.confirm(`Deseja excluir ${ids.length} venda(s) selecionada(s)?`);
  if (!confirmed) {
    stopLoading();
    return;
  }

  let deleted = 0;
  let failed = 0;
  for (const saleId of ids) {
    try {
      await api(`/api/sales/${saleId}`, "DELETE");
      deleted += 1;
    } catch {
      failed += 1;
    }
  }
  state.selectedSaleIds.clear();
  if (state.editingSaleId && ids.includes(state.editingSaleId)) {
    resetSaleFormMode();
  }
  await refreshCore();
  setFeedback(`Vendas excluidas: ${deleted}. Falhas: ${failed}.`, failed > 0);
  stopLoading();
}

async function deleteSelectedFinanceEntries() {
  const stopLoading = setButtonLoading($("#deleteSelectedFinanceBtn"), true, "Excluindo...");
  const ids = Array.from(state.selectedFinanceIds);
  if (!ids.length) {
    stopLoading();
    setFeedback("Selecione ao menos um lançamento financeiro.", true);
    return;
  }
  const confirmed = window.confirm(`Deseja excluir ${ids.length} lançamento(s) financeiro(s) selecionado(s)?`);
  if (!confirmed) {
    stopLoading();
    return;
  }

  let deleted = 0;
  let failed = 0;
  for (const financeId of ids) {
    try {
      await api(`/api/finance/entries/${financeId}`, "DELETE");
      deleted += 1;
    } catch {
      failed += 1;
    }
  }
  state.selectedFinanceIds.clear();
  await refreshCore();
  setFeedback(`Lançamentos excluidos: ${deleted}. Falhas: ${failed}.`, failed > 0);
  stopLoading();
}

async function updateCategoryStatusBulk(targetStatus) {
  const buttonId = targetStatus === "active" ? "#reactivateSelectedCategoriesBtn" : "#deactivateSelectedCategoriesBtn";
  const stopLoading = setButtonLoading($(buttonId), true, targetStatus === "active" ? "Reativando..." : "Inativando...");
  const ids = Array.from(state.selectedCategoryIds);
  if (!ids.length) {
    stopLoading();
    setFeedback("Selecione ao menos uma categoria.", true);
    return;
  }
  const actionLabel = targetStatus === "active" ? "reativar" : "inativar";
  const confirmed = window.confirm(`Deseja ${actionLabel} ${ids.length} categoria(s) selecionada(s)?`);
  if (!confirmed) {
    stopLoading();
    return;
  }
  let updated = 0;
  let failed = 0;
  for (const id of ids) {
    const row = state.categories.find((item) => Number(item.id) === Number(id));
    if (!row) {
      failed += 1;
      continue;
    }
    try {
      await api(`/api/categories/${id}`, "PUT", {
        name: row.name || "",
        description: row.description || "",
        status: targetStatus,
      });
      updated += 1;
    } catch {
      failed += 1;
    }
  }
  state.selectedCategoryIds.clear();
  renderCategories();
  await refreshCore();
  setFeedback(`Categorias ${targetStatus === "active" ? "reativadas" : "inativadas"}: ${updated}. Falhas: ${failed}.`, failed > 0);
  stopLoading();
}

async function deleteSelectedCategories() {
  const stopLoading = setButtonLoading($("#deleteSelectedCategoriesBtn"), true, "Excluindo...");
  const ids = Array.from(state.selectedCategoryIds);
  if (!ids.length) {
    stopLoading();
    setFeedback("Selecione ao menos uma categoria.", true);
    return;
  }
  const confirmed = window.confirm(`Deseja excluir ${ids.length} categoria(s) selecionada(s)?`);
  if (!confirmed) {
    stopLoading();
    return;
  }
  let deleted = 0;
  let deactivated = 0;
  let failed = 0;
  for (const id of ids) {
    try {
      const result = await api(`/api/categories/${id}`, "DELETE");
      if (result.mode === "deactivated") deactivated += 1;
      else deleted += 1;
    } catch {
      failed += 1;
    }
  }
  state.selectedCategoryIds.clear();
  renderCategories();
  await refreshCore();
  setFeedback(`Categorias processadas: ${deleted} excluida(s), ${deactivated} inativada(s), ${failed} falha(s).`, failed > 0);
  stopLoading();
}

async function updateSupplierStatusBulk(targetActive) {
  const buttonId = targetActive ? "#reactivateSelectedSuppliersBtn" : "#deactivateSelectedSuppliersBtn";
  const stopLoading = setButtonLoading($(buttonId), true, targetActive ? "Reativando..." : "Inativando...");
  const ids = Array.from(state.selectedSupplierIds);
  if (!ids.length) {
    stopLoading();
    setFeedback("Selecione ao menos um fornecedor.", true);
    return;
  }
  const actionLabel = targetActive ? "reativar" : "inativar";
  const confirmed = window.confirm(`Deseja ${actionLabel} ${ids.length} fornecedor(es) selecionado(s)?`);
  if (!confirmed) {
    stopLoading();
    return;
  }
  let updated = 0;
  let failed = 0;
  for (const id of ids) {
    const row = state.suppliers.find((item) => Number(item.id) === Number(id));
    if (!row) {
      failed += 1;
      continue;
    }
    try {
      await api(`/api/suppliers/${id}`, "PUT", {
        name: row.name || "",
        contact: row.contact || "",
        phone: row.phone || "",
        email: row.email || "",
        notes: row.notes || "",
        is_active: targetActive,
      });
      updated += 1;
    } catch {
      failed += 1;
    }
  }
  state.selectedSupplierIds.clear();
  renderSuppliers();
  await refreshCore();
  setFeedback(`Fornecedores ${targetActive ? "reativados" : "inativados"}: ${updated}. Falhas: ${failed}.`, failed > 0);
  stopLoading();
}

async function deleteSelectedSuppliers() {
  const stopLoading = setButtonLoading($("#deleteSelectedSuppliersBtn"), true, "Excluindo...");
  const ids = Array.from(state.selectedSupplierIds);
  if (!ids.length) {
    stopLoading();
    setFeedback("Selecione ao menos um fornecedor.", true);
    return;
  }
  const confirmed = window.confirm(`Deseja excluir ${ids.length} fornecedor(es) selecionado(s)?`);
  if (!confirmed) {
    stopLoading();
    return;
  }
  let deleted = 0;
  let deactivated = 0;
  let failed = 0;
  for (const id of ids) {
    try {
      const result = await api(`/api/suppliers/${id}`, "DELETE");
      if (result.mode === "deactivated") deactivated += 1;
      else deleted += 1;
    } catch {
      failed += 1;
    }
  }
  state.selectedSupplierIds.clear();
  renderSuppliers();
  await refreshCore();
  setFeedback(`Fornecedores processados: ${deleted} excluido(s), ${deactivated} inativado(s), ${failed} falha(s).`, failed > 0);
  stopLoading();
}

async function deleteSelectedPurchases() {
  const stopLoading = setButtonLoading($("#deleteSelectedPurchasesBtn"), true, "Excluindo...");
  const ids = Array.from(state.selectedPurchaseIds);
  if (!ids.length) {
    stopLoading();
    setFeedback("Selecione ao menos uma compra.", true);
    return;
  }
  const confirmed = window.confirm(`Deseja excluir ${ids.length} compra(s) selecionada(s)?`);
  if (!confirmed) {
    stopLoading();
    return;
  }
  let deleted = 0;
  let failed = 0;
  for (const id of ids) {
    try {
      await api(`/api/purchases/${id}`, "DELETE");
      deleted += 1;
    } catch {
      failed += 1;
    }
  }
  state.selectedPurchaseIds.clear();
  renderPurchases();
  await refreshCore();
  setFeedback(`Compras excluídas: ${deleted}. Falhas: ${failed}.`, failed > 0);
  stopLoading();
}

function buildUserUpdatePayload(row, extra = {}) {
  return {
    name: row.name || "",
    role: row.role || "member",
    module_permissions: Array.isArray(row.module_permissions) ? row.module_permissions : [],
    avatar_url: row.avatar_url || null,
    ...extra,
  };
}

async function reactivateUser(row, { refresh = true } = {}) {
  const userId = Number(row?.id);
  if (!userId) throw new Error("Usuário inválido para reativação.");
  const result = await api(`/api/users/${userId}/reactivate`, "PUT");
  if (refresh) await refreshCore();
  return result?.mode || "reactivated";
}

async function hardDeleteUser(row, { refresh = true } = {}) {
  const userId = Number(row?.id);
  if (!userId) throw new Error("Usuário inválido para exclusão.");
  const result = await api(`/api/users/${userId}?mode=delete`, "DELETE");
  if (refresh) await refreshCore();
  return result?.mode || "deleted";
}

async function deactivateSelectedUsers() {
  const stopLoading = setButtonLoading($("#deactivateSelectedUsersBtn"), true, "Inativando...");
  const ids = Array.from(state.selectedUserIds);
  if (!ids.length) {
    stopLoading();
    setFeedback("Selecione ao menos um usuário.", true);
    return;
  }
  const confirmed = window.confirm(`Deseja inativar ${ids.length} usuário(s) selecionado(s)?`);
  if (!confirmed) {
    stopLoading();
    return;
  }

  let deactivated = 0;
  let failed = 0;
  for (const userId of ids) {
    try {
      await api(`/api/users/${userId}/deactivate`, "PUT");
      deactivated += 1;
    } catch {
      failed += 1;
    }
  }
  state.selectedUserIds.clear();
  renderUsers();
  await refreshCore();
  setFeedback(`Usuários inativados: ${deactivated}. Falhas: ${failed}.`, failed > 0);
  stopLoading();
}

async function reactivateSelectedUsers() {
  const stopLoading = setButtonLoading($("#reactivateSelectedUsersBtn"), true, "Reativando...");
  const ids = Array.from(state.selectedUserIds);
  if (!ids.length) {
    stopLoading();
    setFeedback("Selecione ao menos um usuário.", true);
    return;
  }
  const confirmed = window.confirm(`Deseja reativar ${ids.length} usuário(s) selecionado(s)?`);
  if (!confirmed) {
    stopLoading();
    return;
  }

  let reactivated = 0;
  let failed = 0;
  for (const userId of ids) {
    const row = state.users.find((u) => Number(u.id) === Number(userId));
    if (!row) {
      failed += 1;
      continue;
    }
    try {
      await reactivateUser(row, { refresh: false });
      reactivated += 1;
    } catch {
      failed += 1;
    }
  }
  state.selectedUserIds.clear();
  renderUsers();
  await refreshCore();
  setFeedback(`Usuários reativados: ${reactivated}. Falhas: ${failed}.`, failed > 0);
  stopLoading();
}

async function deleteSelectedUsers() {
  const stopLoading = setButtonLoading($("#deleteSelectedUsersBtn"), true, "Excluindo...");
  const ids = Array.from(state.selectedUserIds);
  if (!ids.length) {
    stopLoading();
    setFeedback("Selecione ao menos um usuário.", true);
    return;
  }
  const confirmed = window.confirm(
    `Deseja excluir definitivamente ${ids.length} usuário(s) selecionado(s)? Esta ação depende de endpoint específico.`
  );
  if (!confirmed) {
    stopLoading();
    return;
  }

  let deleted = 0;
  let inactivated = 0;
  let failed = 0;
  for (const userId of ids) {
    const row = state.users.find((u) => Number(u.id) === Number(userId));
    if (!row) {
      failed += 1;
      continue;
    }
    try {
      const mode = await hardDeleteUser(row, { refresh: false });
      if (mode === "deleted") {
        deleted += 1;
      } else if (mode === "deactivated" || mode === "already_inactive") {
        inactivated += 1;
      } else {
        deleted += 1;
      }
    } catch {
      failed += 1;
    }
  }
  state.selectedUserIds.clear();
  renderUsers();
  await refreshCore();
  setFeedback(
    `Usuários excluídos: ${deleted}. Inativados por segurança: ${inactivated}. Falhas: ${failed}.`,
    failed > 0
  );
  stopLoading();
}

function renderSales() {
  if (!state.salesEndpointAvailable) {
    $("#salesTable").innerHTML =
      "<div class='empty-state'>Historico de vendas indisponivel nesta instancia do servidor. Reinicie a aplicacao com a versao mais recente.</div>";
    return;
  }

  const filtered = getFilteredSales();
  const visibleIds = new Set(filtered.map((item) => Number(item.id)));
  state.selectedSaleIds.forEach((id) => {
    if (!visibleIds.has(Number(id))) {
      state.selectedSaleIds.delete(id);
    }
  });

  const canManage = canAccessModule("sales");
  const deleteSelectedBtn = $("#deleteSelectedSalesBtn");
  if (deleteSelectedBtn) {
    deleteSelectedBtn.disabled = !canManage || state.selectedSaleIds.size === 0;
    deleteSelectedBtn.textContent =
      state.selectedSaleIds.size > 0 ? `Excluir selecionados (${state.selectedSaleIds.size})` : "Excluir selecionados";
  }
  $("#salesTable").innerHTML = filtered.length
    ? `<table>
      <thead>
        <tr>
          ${canManage ? "<th><input type='checkbox' id='selectAllSales' /></th>" : ""}
          <th>Data</th>
          <th>Produto</th>
          <th>SKU</th>
          <th>Cód. barras</th>
          <th>Quantidade</th>
          <th>Preco unitario</th>
          <th>Total</th>
          <th>Custo vendido</th>
          <th>Taxas/Impostos</th>
          <th>Lucro bruto</th>
          <th>Lucro liquido</th>
          <th>Status</th>
          ${canManage ? "<th>Acoes</th>" : ""}
        </tr>
      </thead>
      <tbody>${filtered
        .map(
          (sale) => `<tr class="${state.selectedSaleIds.has(Number(sale.id)) ? "is-selected" : ""}">
            ${
              canManage
                ? `<td><input type="checkbox" class="sale-check" data-sale-check="${sale.id}" ${
                    state.selectedSaleIds.has(Number(sale.id)) ? "checked" : ""
                  } /></td>`
                : ""
            }
            <td>${formatDate(sale.created_at)}</td>
            <td>${escapeHtml(sale.product_name)}</td>
            <td>${escapeHtml(sale.sku || "-")}</td>
            <td>${escapeHtml(sale.barcode || "-")}</td>
            <td>${sale.qty}</td>
            <td>${formatMoney(sale.unit_price)}</td>
            <td>${formatMoney(sale.total)}</td>
            <td>${formatMoney(sale.cogs_total || 0)}</td>
            <td>${formatMoney((sale.taxes_total || 0) + (sale.extra_expenses_total || 0))}</td>
            <td>${formatMoney(sale.gross_profit || 0)}</td>
            <td>${formatMoney(sale.net_profit || 0)}</td>
            <td><span class="badge">Concluida</span></td>
            ${
              canManage
                ? `<td>
              <div class="table-actions">
                <button class="btn-inline edit" data-edit-sale="${sale.id}">Editar</button>
                <button class="btn-inline delete" data-delete-sale="${sale.id}">Excluir</button>
              </div>
            </td>`
                : ""
            }
          </tr>`
        )
        .join("")}</tbody>
    </table>`
    : "<div class='empty-state'>Nenhuma venda registrada.</div>";

  if (!canManage || !filtered.length) return;

  const selectAll = $("#selectAllSales");
  if (selectAll) {
    const selectedVisible = filtered.filter((row) => state.selectedSaleIds.has(Number(row.id))).length;
    setSelectAllState(selectAll, selectedVisible, filtered.length);
    selectAll.addEventListener("change", () => {
      if (selectAll.checked) {
        filtered.forEach((row) => state.selectedSaleIds.add(Number(row.id)));
      } else {
        filtered.forEach((row) => state.selectedSaleIds.delete(Number(row.id)));
      }
      renderSales();
    });
  }

  $$(".sale-check").forEach((check) => {
    check.addEventListener("change", () => {
      const saleId = Number(check.dataset.saleCheck);
      if (Number.isNaN(saleId)) return;
      if (check.checked) {
        state.selectedSaleIds.add(saleId);
      } else {
        state.selectedSaleIds.delete(saleId);
      }
      renderSales();
    });
  });

  $$("[data-edit-sale]").forEach((button) => {
    button.addEventListener("click", () => {
      const saleId = Number(button.dataset.editSale);
      const sale = state.sales.find((item) => Number(item.id) === saleId);
      if (!sale) return;
      setSaleEditMode(sale);
      setFeedback(`Venda #${sale.id} carregada para edicao.`);
    });
  });

  $$("[data-delete-sale]").forEach((button) => {
    button.addEventListener("click", async () => {
      const saleId = Number(button.dataset.deleteSale);
      const sale = state.sales.find((item) => Number(item.id) === saleId);
      if (!sale) return;
      const confirmed = window.confirm(`Deseja realmente excluir a venda #${sale.id}?`);
      if (!confirmed) return;

      try {
        await api(`/api/sales/${saleId}`, "DELETE");
        if (state.editingSaleId === saleId) {
          resetSaleFormMode();
        }
        await refreshCore();
        state.selectedSaleIds.delete(saleId);
        setFeedback(`Venda #${sale.id} excluida com sucesso.`);
      } catch (error) {
        setFeedback(error.message, true);
      }
    });
  });
}

function renderFinance() {
  const canManage = canAccessModule("finance");
  const filtered = getFilteredFinanceEntries();
  const incomeTotal = filtered
    .filter((entry) => entry.entry_type === "income")
    .reduce((acc, entry) => acc + Number(entry.amount || 0), 0);
  const expenseTotal = filtered
    .filter((entry) => entry.entry_type === "expense")
    .reduce((acc, entry) => acc + Number(entry.amount || 0), 0);
  const receivable = filtered
    .filter((entry) => entry.entry_type === "income" && String(entry.payment_status || "").toLowerCase() !== "pago")
    .reduce((acc, entry) => acc + Number(entry.amount || 0), 0);
  const payable = filtered
    .filter((entry) => entry.entry_type === "expense" && String(entry.payment_status || "").toLowerCase() !== "pago")
    .reduce((acc, entry) => acc + Number(entry.amount || 0), 0);
  const financeSummary = $("#financeSummaryKpis");
  if (financeSummary) {
    financeSummary.innerHTML = `
      <article class="metric"><p class="label">Entradas do período</p><p class="value">${formatMoney(incomeTotal)}</p></article>
      <article class="metric"><p class="label">Saídas do período</p><p class="value">${formatMoney(expenseTotal)}</p></article>
      <article class="metric"><p class="label">Saldo do período</p><p class="value">${formatMoney(incomeTotal - expenseTotal)}</p></article>
      <article class="metric"><p class="label">Contas a receber</p><p class="value">${formatMoney(receivable)}</p></article>
      <article class="metric"><p class="label">Contas a pagar</p><p class="value">${formatMoney(payable)}</p></article>
    `;
  }

  const visibleIds = new Set(filtered.map((item) => Number(item.id)));
  state.selectedFinanceIds.forEach((id) => {
    if (!visibleIds.has(Number(id))) {
      state.selectedFinanceIds.delete(id);
    }
  });
  const deleteSelectedBtn = $("#deleteSelectedFinanceBtn");
  if (deleteSelectedBtn) {
    deleteSelectedBtn.disabled = !canManage || state.selectedFinanceIds.size === 0;
    deleteSelectedBtn.textContent =
      state.selectedFinanceIds.size > 0 ? `Excluir selecionados (${state.selectedFinanceIds.size})` : "Excluir selecionados";
  }

  $("#financeTable").innerHTML = filtered.length
    ? `<table>
      <thead><tr>${canManage ? "<th><input type='checkbox' id='selectAllFinance' /></th>" : ""}<th>Data</th><th>Tipo</th><th>Categoria</th><th>Descricao</th><th>Valor</th><th>Pagamento</th><th>Condição</th><th>Status</th><th>Origem</th>${canManage ? "<th>Acoes</th>" : ""}</tr></thead>
      <tbody>${filtered
        .map(
          (entry) => {
            const entryLabel = entry.entry_type === "income" ? "Ganho" : "Gasto";
            return `<tr class="${state.selectedFinanceIds.has(Number(entry.id)) ? "is-selected" : ""}">
            ${
              canManage
                ? `<td><input type="checkbox" class="finance-check" data-finance-check="${entry.id}" ${
                    state.selectedFinanceIds.has(Number(entry.id)) ? "checked" : ""
                  } /></td>`
                : ""
            }
            <td>${formatDate(entry.created_at)}</td>
            <td><span class="badge ${entry.entry_type}">${entryLabel}</span></td>
            <td>${escapeHtml(entry.category)}</td>
            <td>${escapeHtml(entry.description || "-")}</td>
            <td>${formatMoney(entry.amount)}</td>
            <td>${escapeHtml(entry.payment_method || "-")}</td>
            <td>${escapeHtml(entry.payment_terms || "-")}</td>
            <td><span class="badge">${escapeHtml(entry.payment_status || "-")}</span></td>
            <td>${escapeHtml(entry.origin || "manual")}</td>
            ${
              canManage
                ? `<td>
              <div class="table-actions">
                <button class="btn-inline edit" data-edit-finance="${entry.id}">Editar</button>
                <button class="btn-inline delete" data-delete-finance="${entry.id}">Excluir</button>
              </div>
            </td>`
                : ""
            }
          </tr>`;
          }
        )
        .join("")}</tbody>
    </table>`
    : "<div class='empty-state'>Nenhum lancamento encontrado.</div>";

  if (!canManage || !filtered.length) return;

  const selectAll = $("#selectAllFinance");
  if (selectAll) {
    const selectedVisible = filtered.filter((row) => state.selectedFinanceIds.has(Number(row.id))).length;
    setSelectAllState(selectAll, selectedVisible, filtered.length);
    selectAll.addEventListener("change", () => {
      if (selectAll.checked) {
        filtered.forEach((row) => state.selectedFinanceIds.add(Number(row.id)));
      } else {
        filtered.forEach((row) => state.selectedFinanceIds.delete(Number(row.id)));
      }
      renderFinance();
    });
  }

  $$(".finance-check").forEach((check) => {
    check.addEventListener("change", () => {
      const financeId = Number(check.dataset.financeCheck);
      if (Number.isNaN(financeId)) return;
      if (check.checked) {
        state.selectedFinanceIds.add(financeId);
      } else {
        state.selectedFinanceIds.delete(financeId);
      }
      renderFinance();
    });
  });

  $$("[data-edit-finance]").forEach((button) => {
    button.addEventListener("click", async () => {
      const financeId = Number(button.dataset.editFinance);
      const entry = state.financeEntries.find((item) => Number(item.id) === financeId);
      if (!entry) return;

      const newCategory = window.prompt("Categoria:", entry.category || "");
      if (newCategory === null) return;
      const newDescription = window.prompt("Descricao:", entry.description || "");
      if (newDescription === null) return;
      const newAmountRaw = window.prompt("Valor (R$):", String(Number(entry.amount || 0)));
      if (newAmountRaw === null) return;
      const newAmount = Number(newAmountRaw);
      if (!Number.isFinite(newAmount) || newAmount <= 0) {
        setFeedback("Valor invalido para lancamento.", true);
        return;
      }
      const newDate = window.prompt("Data e hora (YYYY-MM-DDTHH:mm):", toDateTimeLocalFromIso(entry.created_at));
      if (newDate === null) return;
      if (!newDate.trim()) {
        setFeedback("Data e hora sao obrigatorias.", true);
        return;
      }
      const newMethod = window.prompt("Forma de pagamento:", entry.payment_method || "N/A");
      if (newMethod === null) return;
      const newTerms = window.prompt("Condição de pagamento:", entry.payment_terms || "À vista");
      if (newTerms === null) return;
      const newStatus = window.prompt("Status (pago/pendente/parcial/vencido):", entry.payment_status || "pago");
      if (newStatus === null) return;
      const newNotes = window.prompt("Observações:", entry.notes || "");
      if (newNotes === null) return;

      try {
        await api(`/api/finance/entries/${financeId}`, "PUT", {
          entry_type: entry.entry_type,
          category: newCategory.trim(),
          description: newDescription.trim(),
          amount: newAmount,
          created_at: newDate.trim(),
          payment_method: newMethod.trim(),
          payment_terms: newTerms.trim(),
          payment_status: newStatus.trim(),
          notes: newNotes.trim(),
        });
        await refreshCore();
        setFeedback("Lancamento financeiro atualizado com sucesso.");
      } catch (error) {
        setFeedback(error.message, true);
        window.alert(error.message);
      }
    });
  });

  $$("[data-delete-finance]").forEach((button) => {
    button.addEventListener("click", async () => {
      const financeId = Number(button.dataset.deleteFinance);
      const entry = state.financeEntries.find((item) => Number(item.id) === financeId);
      if (!entry) return;

      const confirmed = window.confirm("Deseja realmente excluir este lancamento financeiro?");
      if (!confirmed) return;

      try {
        await api(`/api/finance/entries/${financeId}`, "DELETE");
        await refreshCore();
        state.selectedFinanceIds.delete(financeId);
        setFeedback("Lancamento financeiro excluido com sucesso.");
      } catch (error) {
        setFeedback(error.message, true);
        window.alert(error.message);
      }
    });
  });
}

function renderUsers() {
  const canManageUsers = state.user?.role === "master";
  const filtered = getFilteredUsers();
  const visibleIds = new Set(filtered.map((item) => Number(item.id)));
  state.selectedUserIds.forEach((id) => {
    if (!visibleIds.has(Number(id))) {
      state.selectedUserIds.delete(id);
    }
  });
  const selectedCount = state.selectedUserIds.size;
  const deactivateBtn = $("#deactivateSelectedUsersBtn");
  const reactivateBtn = $("#reactivateSelectedUsersBtn");
  const deleteBtn = $("#deleteSelectedUsersBtn");
  if (deactivateBtn) {
    deactivateBtn.disabled = !canManageUsers || selectedCount === 0;
    deactivateBtn.textContent = selectedCount > 0 ? `Inativar selecionados (${selectedCount})` : "Inativar selecionados";
  }
  if (reactivateBtn) {
    reactivateBtn.disabled = !canManageUsers || selectedCount === 0;
    reactivateBtn.textContent = selectedCount > 0 ? `Reativar selecionados (${selectedCount})` : "Reativar selecionados";
  }
  if (deleteBtn) {
    deleteBtn.disabled = !canManageUsers || selectedCount === 0;
    deleteBtn.textContent = selectedCount > 0 ? `Excluir selecionados (${selectedCount})` : "Excluir selecionados";
  }

  $("#usersTable").innerHTML = filtered.length
    ? `<table>
      <thead><tr>${canManageUsers ? "<th><input type='checkbox' id='selectAllUsers' /></th>" : ""}<th>Avatar</th><th>Nome</th><th>Email</th><th>Perfil</th><th>Acessos</th><th>Status</th><th>Criado em</th>${canManageUsers ? "<th>Acoes</th>" : ""}</tr></thead>
      <tbody>${filtered
        .map(
          (user) => {
            const perms = Array.isArray(user.module_permissions) ? user.module_permissions : [];
            const accessSummary = user.role === "master" ? "Completo (8)" : `${perms.length} módulo(s)`;
            const permsLabel = user.role === "master"
              ? "Dashboard, Produtos, Categorias, Calculadora de Custos, Compras/Fornecedores, Estoque, Vendas, Financeiro, Usuários"
              : MODULE_DEFINITIONS.filter((item) => perms.includes(item.key))
                  .map((item) => item.label)
                  .filter((v, i, arr) => arr.indexOf(v) === i)
                  .join(", ") || "Sem módulos liberados";
            return `<tr class="${state.selectedUserIds.has(Number(user.id)) ? "is-selected" : ""}">
            ${
              canManageUsers
                ? `<td><input type="checkbox" class="user-check" data-user-check="${user.id}" ${
                    state.selectedUserIds.has(Number(user.id)) ? "checked" : ""
                  } /></td>`
                : ""
            }
            <td>${renderAvatarHtml(user.name, user.avatar_url, "avatar-table")}</td>
            <td>${escapeHtml(user.name)}</td>
            <td>${escapeHtml(user.email)}</td>
            <td><span class="badge">${escapeHtml(user.role)}</span></td>
            <td><span class="badge" title="${escapeHtml(permsLabel)}">${escapeHtml(accessSummary)}</span></td>
            <td><span class="badge">${user.is_active ? "Ativo" : "Inativo"}</span></td>
            <td>${formatDate(user.created_at)}</td>
            ${
              canManageUsers
                ? `<td>
                <div class="table-actions">
                  <button class="btn-inline edit" data-edit-user="${user.id}">Editar</button>
                  <button class="btn-inline edit" data-reset-user-password="${user.id}">Reset senha</button>
                  ${
                    user.is_active
                      ? `<button class="btn-inline delete" data-deactivate-user="${user.id}">Inativar</button>`
                      : `<button class="btn-inline edit" data-reactivate-user="${user.id}">Reativar</button>
                         <button class="btn-inline delete" data-delete-user="${user.id}">Excluir</button>`
                  }
                </div>
              </td>`
                : ""
            }
          </tr>`;
          }
        )
        .join("")}</tbody>
    </table>`
    : "<div class='empty-state'>Nenhum usuario encontrado.</div>";

  if (!canManageUsers || !filtered.length) return;

  const selectAll = $("#selectAllUsers");
  if (selectAll) {
    const selectedVisible = filtered.filter((row) => state.selectedUserIds.has(Number(row.id))).length;
    setSelectAllState(selectAll, selectedVisible, filtered.length);
    selectAll.addEventListener("change", () => {
      if (selectAll.checked) {
        filtered.forEach((row) => state.selectedUserIds.add(Number(row.id)));
      } else {
        filtered.forEach((row) => state.selectedUserIds.delete(Number(row.id)));
      }
      renderUsers();
    });
  }

  $$(".user-check").forEach((check) => {
    check.addEventListener("change", () => {
      const userId = Number(check.dataset.userCheck);
      if (Number.isNaN(userId)) return;
      if (check.checked) {
        state.selectedUserIds.add(userId);
      } else {
        state.selectedUserIds.delete(userId);
      }
      renderUsers();
    });
  });

  $$("[data-edit-user]").forEach((button) => {
    button.addEventListener("click", () => {
      const userId = Number(button.dataset.editUser);
      const row = state.users.find((u) => Number(u.id) === userId);
      if (!row) return;
      setUserEditMode(row);
      setFeedback(`Editando permissões de ${row.name}.`);
    });
  });

  $$("[data-deactivate-user]").forEach((button) => {
    button.addEventListener("click", async () => {
      const userId = Number(button.dataset.deactivateUser);
      const row = state.users.find((u) => Number(u.id) === userId);
      if (!row) return;
      const confirmed = window.confirm(`Deseja inativar o usuario "${row.name}"?`);
      if (!confirmed) return;
      try {
        await api(`/api/users/${userId}/deactivate`, "PUT");
        state.selectedUserIds.delete(userId);
        renderUsers();
        await refreshCore();
        setFeedback("Usuário inativado com sucesso.");
      } catch (error) {
        setFeedback(error.message, true);
      }
    });
  });

  $$("[data-reactivate-user]").forEach((button) => {
    button.addEventListener("click", async () => {
      const userId = Number(button.dataset.reactivateUser);
      const row = state.users.find((u) => Number(u.id) === userId);
      if (!row) return;
      const confirmed = window.confirm(`Deseja reativar o usuario "${row.name}"?`);
      if (!confirmed) return;
      try {
        await reactivateUser(row);
        setFeedback("Usuário reativado com sucesso.");
      } catch (error) {
        setFeedback(error.message, true);
      }
    });
  });

  $$("[data-delete-user]").forEach((button) => {
    button.addEventListener("click", async () => {
      const userId = Number(button.dataset.deleteUser);
      const row = state.users.find((u) => Number(u.id) === userId);
      if (!row) return;
      const confirmed = window.confirm(
        `Deseja excluir o usuario "${row.name}"? Se houver histórico crítico, ele será apenas inativado por segurança.`
      );
      if (!confirmed) return;
      try {
        const mode = await hardDeleteUser(row);
        if (mode === "deactivated" || mode === "already_inactive") {
          setFeedback("Usuário inativado por segurança para preservar o histórico.");
        } else {
          setFeedback("Usuário excluído com sucesso.");
        }
      } catch (error) {
        setFeedback(error.message, true);
      }
    });
  });

  $$("[data-reset-user-password]").forEach((button) => {
    button.addEventListener("click", async () => {
      const userId = Number(button.dataset.resetUserPassword);
      const row = state.users.find((u) => Number(u.id) === userId);
      if (!row) return;
      const newPassword = window.prompt(`Nova senha para ${row.name}:`, "1234");
      if (newPassword === null) return;
      try {
        await api(`/api/users/${userId}/reset-password`, "PUT", { new_password: newPassword });
        setFeedback("Senha redefinida com sucesso.");
      } catch (error) {
        setFeedback(error.message, true);
      }
    });
  });
}

function renderCategories() {
  const wrap = $("#categoriesTable");
  if (!wrap) return;
  const canManage = canAccessModule("products");
  const query = normalizeText($("#categorySearch")?.value || "");
  const filtered = state.categories.filter((c) => {
    if (!query) return true;
    return normalizeText(`${c.name || ""} ${c.description || ""}`).includes(query);
  });
  const visibleIds = new Set(filtered.map((item) => Number(item.id)));
  state.selectedCategoryIds.forEach((id) => {
    if (!visibleIds.has(Number(id))) {
      state.selectedCategoryIds.delete(id);
    }
  });
  const selectedCount = state.selectedCategoryIds.size;
  const deactivateBtn = $("#deactivateSelectedCategoriesBtn");
  const reactivateBtn = $("#reactivateSelectedCategoriesBtn");
  const deleteBtn = $("#deleteSelectedCategoriesBtn");
  if (deactivateBtn) {
    deactivateBtn.disabled = !canManage || selectedCount === 0;
    deactivateBtn.textContent = selectedCount > 0 ? `Inativar selecionadas (${selectedCount})` : "Inativar selecionadas";
  }
  if (reactivateBtn) {
    reactivateBtn.disabled = !canManage || selectedCount === 0;
    reactivateBtn.textContent = selectedCount > 0 ? `Reativar selecionadas (${selectedCount})` : "Reativar selecionadas";
  }
  if (deleteBtn) {
    deleteBtn.disabled = !canManage || selectedCount === 0;
    deleteBtn.textContent = selectedCount > 0 ? `Excluir selecionadas (${selectedCount})` : "Excluir selecionadas";
  }
  if (!filtered.length) {
    wrap.innerHTML = "<div class='empty-state'>Nenhuma categoria encontrada.</div>";
    return;
  }
  wrap.innerHTML = `<table>
    <thead><tr>${canManage ? "<th><input type='checkbox' id='selectAllCategories' /></th>" : ""}<th>Categoria</th><th>Descrição</th><th>Status</th><th>Produtos vinculados</th><th>Criada em</th>${canManage ? "<th>Ações</th>" : ""}</tr></thead>
    <tbody>${filtered
      .map(
        (c) => `<tr class="${state.selectedCategoryIds.has(Number(c.id)) ? "is-selected" : ""}">
        ${
          canManage
            ? `<td><input type="checkbox" class="category-check" data-category-check="${c.id}" ${
                state.selectedCategoryIds.has(Number(c.id)) ? "checked" : ""
              } /></td>`
            : ""
        }
        <td>${escapeHtml(c.name)}</td>
        <td>${escapeHtml(c.description || "-")}</td>
        <td><span class="badge">${Number(c.is_active || 0) === 1 ? "Ativa" : "Inativa"}</span></td>
        <td>${Number(c.products_count || 0)}</td>
        <td>${formatDate(c.created_at)}</td>
        ${
          canManage
            ? `<td>
          <div class="table-actions">
            <button class="btn-inline edit" data-edit-category="${c.id}">Editar</button>
            <button class="btn-inline delete" data-delete-category="${c.id}">Excluir</button>
          </div>
        </td>`
            : ""
        }
      </tr>`
      )
      .join("")}</tbody>
  </table>`;

  if (canManage) {
    const selectAll = $("#selectAllCategories");
    if (selectAll) {
      const selectedVisible = filtered.filter((row) => state.selectedCategoryIds.has(Number(row.id))).length;
      setSelectAllState(selectAll, selectedVisible, filtered.length);
      selectAll.addEventListener("change", () => {
        if (selectAll.checked) {
          filtered.forEach((row) => state.selectedCategoryIds.add(Number(row.id)));
        } else {
          filtered.forEach((row) => state.selectedCategoryIds.delete(Number(row.id)));
        }
        renderCategories();
      });
    }
    $$(".category-check").forEach((check) => {
      check.addEventListener("change", () => {
        const id = Number(check.dataset.categoryCheck);
        if (Number.isNaN(id)) return;
        if (check.checked) {
          state.selectedCategoryIds.add(id);
        } else {
          state.selectedCategoryIds.delete(id);
        }
        renderCategories();
      });
    });
  }

  if (!canManage) return;

  $$("[data-edit-category]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.editCategory);
      const row = state.categories.find((c) => Number(c.id) === id);
      if (!row) return;
      setCategoryEditMode(row);
      setFeedback(`Editando categoria ${row.name}.`);
    });
  });

  $$("[data-delete-category]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.deleteCategory);
      const row = state.categories.find((c) => Number(c.id) === id);
      if (!row) return;
      const confirmed = window.confirm(`Deseja excluir a categoria "${row.name}"?`);
      if (!confirmed) return;
      try {
        const result = await api(`/api/categories/${id}`, "DELETE");
        state.selectedCategoryIds.delete(id);
        renderCategories();
        await refreshCore();
        if (result.mode === "deactivated") {
          setFeedback(`Categoria ${row.name} inativada para preservar produtos vinculados.`);
          return;
        }
        setFeedback(`Categoria ${row.name} excluída com sucesso.`);
      } catch (error) {
        setFeedback(error.message, true);
      }
    });
  });
}

function renderStockPosition() {
  const wrap = $("#stockPositionTable");
  if (!wrap) return;
  const query = normalizeText($("#stockPositionSearch")?.value || "");
  const filtered = state.products.filter((p) => {
    if (!query) return true;
    return normalizeText(`${p.name || ""} ${p.sku || ""} ${p.barcode || ""} ${p.category || ""}`).includes(query);
  });
  if (!filtered.length) {
    wrap.innerHTML = "<div class='empty-state'>Nenhum produto encontrado para o estoque atual.</div>";
    return;
  }

  wrap.innerHTML = `<table>
    <thead><tr><th>Produto</th><th>SKU</th><th>Cód. barras</th><th>Categoria</th><th>Descrição</th><th>Qtd estoque</th><th>Custo un.</th><th>Valor em estoque</th><th>Status</th></tr></thead>
    <tbody>${filtered
      .map((p) => {
        const qty = Number(p.stock_qty || 0);
        const totalValue = qty * Number(p.cost_price || 0);
        let statusLabel = "Normal";
        if (qty <= 0) statusLabel = "Zerado";
        else if (qty <= 5) statusLabel = "Estoque baixo";
        return `<tr>
          <td>${escapeHtml(p.name || "-")}</td>
          <td>${escapeHtml(p.sku || "-")}</td>
          <td>${escapeHtml(p.barcode || "-")}</td>
          <td>${escapeHtml(p.category || "-")}</td>
          <td>${escapeHtml(p.description || "-")}</td>
          <td>${qty}</td>
          <td>${formatMoney(p.cost_price || 0)}</td>
          <td>${formatMoney(totalValue)}</td>
          <td><span class="badge">${statusLabel}</span></td>
        </tr>`;
      })
      .join("")}</tbody>
  </table>`;
}

function renderSuppliers() {
  const wrap = $("#suppliersTable");
  if (!wrap) return;
  const canManage = canAccessModule("purchases");
  const query = normalizeText($("#supplierSearch")?.value || "");
  const filtered = state.suppliers.filter((s) => {
    if (!query) return true;
    return normalizeText(`${s.name || ""} ${s.contact || ""} ${s.email || ""} ${s.phone || ""}`).includes(query);
  });
  const visibleIds = new Set(filtered.map((item) => Number(item.id)));
  state.selectedSupplierIds.forEach((id) => {
    if (!visibleIds.has(Number(id))) {
      state.selectedSupplierIds.delete(id);
    }
  });
  const selectedCount = state.selectedSupplierIds.size;
  const deactivateBtn = $("#deactivateSelectedSuppliersBtn");
  const reactivateBtn = $("#reactivateSelectedSuppliersBtn");
  const deleteBtn = $("#deleteSelectedSuppliersBtn");
  if (deactivateBtn) {
    deactivateBtn.disabled = !canManage || selectedCount === 0;
    deactivateBtn.textContent = selectedCount > 0 ? `Inativar selecionados (${selectedCount})` : "Inativar selecionados";
  }
  if (reactivateBtn) {
    reactivateBtn.disabled = !canManage || selectedCount === 0;
    reactivateBtn.textContent = selectedCount > 0 ? `Reativar selecionados (${selectedCount})` : "Reativar selecionados";
  }
  if (deleteBtn) {
    deleteBtn.disabled = !canManage || selectedCount === 0;
    deleteBtn.textContent = selectedCount > 0 ? `Excluir selecionados (${selectedCount})` : "Excluir selecionados";
  }
  if (!filtered.length) {
    wrap.innerHTML = "<div class='empty-state'>Nenhum fornecedor cadastrado.</div>";
    return;
  }
  wrap.innerHTML = `<table>
    <thead><tr>${canManage ? "<th><input type='checkbox' id='selectAllSuppliers' /></th>" : ""}<th>Nome</th><th>Contato</th><th>Telefone</th><th>Email</th><th>Status</th>${canManage ? "<th>Ações</th>" : ""}</tr></thead>
    <tbody>${filtered
      .map(
        (s) => `<tr class="${state.selectedSupplierIds.has(Number(s.id)) ? "is-selected" : ""}">
        ${
          canManage
            ? `<td><input type="checkbox" class="supplier-check" data-supplier-check="${s.id}" ${
                state.selectedSupplierIds.has(Number(s.id)) ? "checked" : ""
              } /></td>`
            : ""
        }
        <td>${escapeHtml(s.name)}</td>
        <td>${escapeHtml(s.contact || "-")}</td>
        <td>${escapeHtml(s.phone || "-")}</td>
        <td>${escapeHtml(s.email || "-")}</td>
        <td><span class="badge">${Number(s.is_active || 0) === 1 ? "Ativo" : "Inativo"}</span></td>
        ${
          canManage
            ? `<td>
          <div class="table-actions">
            <button class="btn-inline edit" data-edit-supplier="${s.id}">Editar</button>
            <button class="btn-inline delete" data-delete-supplier="${s.id}">Excluir</button>
          </div>
        </td>`
            : ""
        }
      </tr>`
      )
      .join("")}</tbody>
  </table>`;

  if (canManage) {
    const selectAll = $("#selectAllSuppliers");
    if (selectAll) {
      const selectedVisible = filtered.filter((row) => state.selectedSupplierIds.has(Number(row.id))).length;
      setSelectAllState(selectAll, selectedVisible, filtered.length);
      selectAll.addEventListener("change", () => {
        if (selectAll.checked) {
          filtered.forEach((row) => state.selectedSupplierIds.add(Number(row.id)));
        } else {
          filtered.forEach((row) => state.selectedSupplierIds.delete(Number(row.id)));
        }
        renderSuppliers();
      });
    }
    $$(".supplier-check").forEach((check) => {
      check.addEventListener("change", () => {
        const id = Number(check.dataset.supplierCheck);
        if (Number.isNaN(id)) return;
        if (check.checked) {
          state.selectedSupplierIds.add(id);
        } else {
          state.selectedSupplierIds.delete(id);
        }
        renderSuppliers();
      });
    });
  }

  if (!canManage) return;

  $$("[data-edit-supplier]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.editSupplier);
      const row = state.suppliers.find((s) => Number(s.id) === id);
      if (!row) return;
      $("#supplierName").value = row.name || "";
      $("#supplierContact").value = row.contact || "";
      $("#supplierPhone").value = row.phone || "";
      $("#supplierEmail").value = row.email || "";
      $("#supplierNotes").value = row.notes || "";
      $("#supplierStatus").value = Number(row.is_active || 0) === 1 ? "active" : "inactive";
      $("#supplierForm").dataset.editingSupplierId = String(id);
      setFeedback(`Fornecedor ${row.name} carregado para edição.`);
    });
  });

  $$("[data-delete-supplier]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.deleteSupplier);
      const row = state.suppliers.find((s) => Number(s.id) === id);
      if (!row) return;
      if (!window.confirm(`Deseja excluir/inativar o fornecedor "${row.name}"?`)) return;
      try {
        const result = await api(`/api/suppliers/${id}`, "DELETE");
        state.selectedSupplierIds.delete(id);
        renderSuppliers();
        await refreshCore();
        setFeedback(result.mode === "deactivated" ? "Fornecedor inativado por histórico." : "Fornecedor excluído.");
      } catch (error) {
        setFeedback(error.message, true);
      }
    });
  });
}

function renderPurchases() {
  const wrap = $("#purchasesTable");
  if (!wrap) return;
  const canManage = canAccessModule("purchases");
  const query = normalizeText($("#purchaseSearch")?.value || "");
  const filtered = state.purchases.filter((p) => {
    if (!query) return true;
    const item = Array.isArray(p.items) && p.items.length ? p.items[0] : null;
    return normalizeText(
      `${p.supplier_name || ""} ${p.purchase_type || ""} ${item?.product_name || ""} ${item?.label || ""} ${p.payment_method || ""} ${
        p.status || ""
      }`
    ).includes(query);
  });
  const visibleIds = new Set(filtered.map((item) => Number(item.id)));
  state.selectedPurchaseIds.forEach((id) => {
    if (!visibleIds.has(Number(id))) {
      state.selectedPurchaseIds.delete(id);
    }
  });
  const selectedCount = state.selectedPurchaseIds.size;
  const deleteBtn = $("#deleteSelectedPurchasesBtn");
  if (deleteBtn) {
    deleteBtn.disabled = !canManage || selectedCount === 0;
    deleteBtn.textContent = selectedCount > 0 ? `Excluir selecionadas (${selectedCount})` : "Excluir selecionadas";
  }
  if (!filtered.length) {
    wrap.innerHTML = "<div class='empty-state'>Nenhuma compra registrada.</div>";
    return;
  }
  wrap.innerHTML = `<table>
    <thead><tr>${canManage ? "<th><input type='checkbox' id='selectAllPurchases' /></th>" : ""}<th>Data</th><th>Fornecedor</th><th>Tipo</th><th>Produto/Descrição</th><th>Qtd</th><th>Custo un.</th><th>Total</th><th>Pagamento</th><th>Status financeiro</th><th>Observação</th><th>Origem</th><th>Impacto</th>${canManage ? "<th>Ações</th>" : ""}</tr></thead>
    <tbody>${filtered
      .map((p) => {
        const item = Array.isArray(p.items) && p.items.length ? p.items[0] : null;
        const itemLabel = item?.product_name || item?.label || "-";
        const stockImpact = p.purchase_type === "inventory" && item?.affects_stock ? "Estoque + Financeiro" : "Somente Financeiro";
        return `<tr class="${state.selectedPurchaseIds.has(Number(p.id)) ? "is-selected" : ""}">
        ${
          canManage
            ? `<td><input type="checkbox" class="purchase-check" data-purchase-check="${p.id}" ${
                state.selectedPurchaseIds.has(Number(p.id)) ? "checked" : ""
              } /></td>`
            : ""
        }
        <td>${formatDate(p.created_at)}</td>
        <td>${escapeHtml(p.supplier_name || "Sem fornecedor")}</td>
        <td>${p.purchase_type === "inventory" ? "Mercadoria" : "Operacional"}</td>
        <td>${escapeHtml(itemLabel)}</td>
        <td>${Number(item?.qty || 0)}</td>
        <td>${formatMoney(item?.unit_cost || 0)}</td>
        <td>${formatMoney(p.total_amount || 0)}</td>
        <td>${escapeHtml(p.payment_method || "-")} / ${escapeHtml(p.payment_terms || "-")}</td>
        <td><span class="badge">${escapeHtml(p.status || "confirmada")}</span></td>
        <td>${escapeHtml(p.notes || "-")}</td>
        <td>${p.purchase_type === "inventory" ? "Compra de mercadoria" : "Compra operacional"}</td>
        <td><span class="badge">${stockImpact}</span></td>
        ${
          canManage
            ? `<td>
          <div class="table-actions">
            <button class="btn-inline edit" data-edit-purchase="${p.id}">Editar</button>
            <button class="btn-inline delete" data-delete-purchase="${p.id}">Excluir</button>
          </div>
        </td>`
            : ""
        }
      </tr>`;
      })
      .join("")}</tbody>
  </table>`;

  if (canManage) {
    const selectAll = $("#selectAllPurchases");
    if (selectAll) {
      const selectedVisible = filtered.filter((row) => state.selectedPurchaseIds.has(Number(row.id))).length;
      setSelectAllState(selectAll, selectedVisible, filtered.length);
      selectAll.addEventListener("change", () => {
        if (selectAll.checked) {
          filtered.forEach((row) => state.selectedPurchaseIds.add(Number(row.id)));
        } else {
          filtered.forEach((row) => state.selectedPurchaseIds.delete(Number(row.id)));
        }
        renderPurchases();
      });
    }
    $$(".purchase-check").forEach((check) => {
      check.addEventListener("change", () => {
        const id = Number(check.dataset.purchaseCheck);
        if (Number.isNaN(id)) return;
        if (check.checked) {
          state.selectedPurchaseIds.add(id);
        } else {
          state.selectedPurchaseIds.delete(id);
        }
        renderPurchases();
      });
    });
  }

  if (!canManage) return;

  $$("[data-edit-purchase]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.editPurchase);
      const row = state.purchases.find((p) => Number(p.id) === id);
      if (!row) return;
      setPurchaseEditMode(row);
      setFeedback(`Compra #${id} carregada para edição.`);
    });
  });

  $$("[data-delete-purchase]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.deletePurchase);
      if (!window.confirm(`Deseja excluir a compra #${id}?`)) return;
      try {
        await api(`/api/purchases/${id}`, "DELETE");
        state.selectedPurchaseIds.delete(id);
        renderPurchases();
        await refreshCore();
        setFeedback("Compra excluída com sucesso.");
      } catch (error) {
        setFeedback(error.message, true);
      }
    });
  });
}

function hideFinanceTooltip() {
  const tooltip = $("#financeTooltip");
  if (!tooltip) return;
  tooltip.classList.add("hidden");
}

function showFinanceTooltip(index, pointerX, pointerY) {
  const tooltip = $("#financeTooltip");
  const wrap = $(".chart-wrap");
  const model = state.financeChartModel;
  if (!tooltip || !wrap || !model || index < 0 || !model.points[index]) {
    hideFinanceTooltip();
    return;
  }

  const point = model.points[index];
  tooltip.innerHTML = `
    <strong>${escapeHtml(point.label)}</strong>
    <div class="chart-tooltip-line"><span>Entradas</span><span>${formatMoney(point.incomes)}</span></div>
    <div class="chart-tooltip-line"><span>Saidas</span><span>${formatMoney(point.expenses)}</span></div>
    <div class="chart-tooltip-line"><span>Liquido</span><span>${formatMoney(point.net)}</span></div>
  `;
  tooltip.classList.remove("hidden");

  const margin = 12;
  const wrapRect = wrap.getBoundingClientRect();
  const tooltipRect = tooltip.getBoundingClientRect();
  let left = pointerX + margin;
  let top = pointerY + margin;

  if (left + tooltipRect.width > wrapRect.width - 8) {
    left = pointerX - tooltipRect.width - margin;
  }
  if (top + tooltipRect.height > wrapRect.height - 8) {
    top = pointerY - tooltipRect.height - margin;
  }

  tooltip.style.left = `${Math.max(8, left)}px`;
  tooltip.style.top = `${Math.max(8, top)}px`;
}

function drawFinanceChart(monthly) {
  const canvas = $("#financeChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 960;
  const height = 290;
  canvas.width = Math.floor(width * ratio);
  canvas.height = Math.floor(height * ratio);
  canvas.style.height = `${height}px`;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);

  if (!monthly.length) {
    state.financeChartModel = null;
    state.financeHoverIndex = -1;
    hideFinanceTooltip();
    ctx.fillStyle = "#8a8f9a";
    ctx.font = "600 14px Plus Jakarta Sans";
    ctx.fillText("Sem dados financeiros para o periodo.", 20, 36);
    return;
  }

  const padding = { top: 30, right: 22, bottom: 42, left: 64 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;
  const rows = monthly.map((item) => {
    const incomes = Number(item.incomes || 0);
    const expenses = Number(item.expenses || 0);
    const net = Number(item.net ?? incomes - expenses);
    return {
      label: item.label || item.month || "-",
      incomes,
      expenses,
      net,
    };
  });

  const allValues = [...rows.map((row) => row.incomes), ...rows.map((row) => row.expenses), ...rows.map((row) => row.net), 0];
  const maxValue = Math.max(...allValues, 1);
  const minValue = Math.min(...allValues, 0);
  const valueRange = maxValue - minValue || 1;
  const yFor = (value) => padding.top + ((maxValue - value) / valueRange) * chartH;
  const zeroY = yFor(0);
  const groupW = chartW / rows.length;
  const barW = Math.min(14, Math.max(6, groupW * 0.25));

  ctx.strokeStyle = "#e9edf4";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#778096";
  ctx.font = "600 11px Plus Jakarta Sans";
  for (let i = 0; i <= 4; i += 1) {
    const ratioY = i / 4;
    const y = padding.top + chartH * ratioY;
    const value = maxValue - valueRange * ratioY;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
    ctx.fillText(formatMoneyShort(value), 8, y + 4);
  }

  ctx.strokeStyle = "#cfd6e2";
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(padding.left, zeroY);
  ctx.lineTo(width - padding.right, zeroY);
  ctx.stroke();

  const skipEvery = rows.length > 18 ? Math.ceil(rows.length / 12) : 1;
  const points = [];
  rows.forEach((row, index) => {
    const centerX = padding.left + groupW * index + groupW / 2;
    const barInX = centerX - barW - 2;
    const barOutX = centerX + 2;
    const inY = yFor(row.incomes);
    const outY = yFor(row.expenses);
    const netY = yFor(row.net);
    const isHover = index === state.financeHoverIndex;

    if (isHover) {
      ctx.fillStyle = "rgba(21, 25, 34, 0.05)";
      ctx.fillRect(centerX - groupW / 2, padding.top, groupW, chartH);
    }

    ctx.fillStyle = "#14161c";
    ctx.fillRect(barInX, Math.min(zeroY, inY), barW, Math.max(1, Math.abs(zeroY - inY)));

    ctx.fillStyle = "#9ea5b4";
    ctx.fillRect(barOutX, Math.min(zeroY, outY), barW, Math.max(1, Math.abs(zeroY - outY)));

    if (index % skipEvery === 0) {
      ctx.fillStyle = "#70798a";
      ctx.font = "600 10px Plus Jakarta Sans";
      ctx.textAlign = "center";
      ctx.fillText(row.label, centerX, height - 14);
    }
    ctx.textAlign = "left";

    points.push({
      left: centerX - groupW / 2,
      right: centerX + groupW / 2,
      centerX,
      netY,
      label: row.label,
      incomes: row.incomes,
      expenses: row.expenses,
      net: row.net,
    });
  });

  ctx.strokeStyle = "#495266";
  ctx.lineWidth = 2.2;
  ctx.beginPath();
  points.forEach((point, index) => {
    if (index === 0) {
      ctx.moveTo(point.centerX, point.netY);
    } else {
      ctx.lineTo(point.centerX, point.netY);
    }
  });
  ctx.stroke();

  ctx.fillStyle = "#495266";
  points.forEach((point, index) => {
    if (rows.length > 16 && index % skipEvery !== 0 && index !== state.financeHoverIndex) return;
    const radius = index === state.financeHoverIndex ? 4 : 2.6;
    ctx.beginPath();
    ctx.arc(point.centerX, point.netY, radius, 0, Math.PI * 2);
    ctx.fill();
  });

  const legendX = width - 205;
  ctx.fillStyle = "#14161c";
  ctx.fillRect(legendX, 16, 11, 11);
  ctx.fillStyle = "#4b5466";
  ctx.font = "600 12px Plus Jakarta Sans";
  ctx.fillText("Entradas", legendX + 17, 25);

  ctx.fillStyle = "#9ea5b4";
  ctx.fillRect(legendX, 34, 11, 11);
  ctx.fillStyle = "#4b5466";
  ctx.fillText("Saidas", legendX + 17, 43);

  ctx.strokeStyle = "#495266";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(legendX, 52);
  ctx.lineTo(legendX + 11, 52);
  ctx.stroke();
  ctx.fillStyle = "#4b5466";
  ctx.fillText("Liquido", legendX + 17, 56);

  state.financeChartModel = { points, width, height };
}

function renderDashboard() {
  if (!state.dashboard) return;

  const kpis = state.dashboard.kpis;
  const noDeductions = Number(kpis.taxes_total || 0) + Number(kpis.expense_total || 0) <= 0.0001;
  const metricItems = [
    {
      label: "Unidades em estoque",
      value: kpis.total_stock_units,
      note: "Soma das quantidades disponiveis no estoque atual.",
      tip: "Total de unidades em estoque: soma de todas as quantidades disponiveis dos produtos.",
    },
    {
      label: "Valor estoque (custo)",
      value: formatMoney(kpis.stock_cost_value ?? kpis.stock_value),
      note: "Baseado no custo unitario multiplicado pelo saldo em estoque.",
      tip: "Formula: soma de (quantidade em estoque x custo unitario).",
    },
    {
      label: "Resultado bruto",
      value: formatMoney(kpis.gross_result ?? kpis.gross_revenue ?? kpis.sales_total),
      note: "Receita total vendida antes de custos, taxas e despesas.",
      tip: "Formula: receita bruta do periodo (antes de deducoes).",
    },
    {
      label: "Resultado liquido",
      value: formatMoney(kpis.net_result),
      note: noDeductions
        ? "Sem taxas/despesas no periodo: bruto e liquido estao iguais."
        : "Receita - custo vendido - taxas/impostos - despesas extras.",
      tip: "Formula: receita total - custo dos produtos vendidos - taxas - impostos - despesas extras.",
    },
    {
      label: "Margem bruta",
      value: `${Number(kpis.gross_margin_percent || 0).toFixed(2)}%`,
      note: "Percentual da receita apos descontar apenas o custo vendido.",
      tip: "Formula: ((receita bruta - custo vendido) / receita bruta) x 100.",
    },
    {
      label: "Margem liquida",
      value: `${Number(kpis.net_margin_percent || 0).toFixed(2)}%`,
      note: "Percentual final apos custos, taxas/impostos e despesas extras.",
      tip: "Formula: (lucro liquido / receita bruta) x 100.",
    },
  ];

  $("#kpiGrid").innerHTML = metricItems
    .map(
      (item) => `<article class="metric">
        <div class="metric-head">
          <p class="label">${item.label}</p>
          <span class="metric-info" title="${escapeHtml(item.tip)}">i</span>
        </div>
        <p class="value">${item.value}</p>
        <p class="metric-note">${item.note}</p>
      </article>`
    )
    .join("");

  drawFinanceChart(state.dashboard.monthly || []);
  const chartSubtitle = $("#financeChartSubtitle");
  if (chartSubtitle) {
    chartSubtitle.textContent = `${state.dashboard.grouping_label || "Agrupado por dia"} • Entradas, saidas e resultado liquido`;
  }
  const chartLegend = $("#financeChartLegend");
  if (chartLegend) {
    chartLegend.innerHTML = `
      <span><i style="background:#14161c"></i>Entradas</span>
      <span><i style="background:#9ea5b4"></i>Saídas</span>
      <span><i style="background:#1f2838"></i>Líquido</span>
    `;
  }

  if (state.activeSection === "dashboard" && state.dashboard.period) {
    $("#pageKicker").textContent = `Periodo ${formatPeriodDate(state.dashboard.period.start)} - ${formatPeriodDate(
      state.dashboard.period.end
    )}`;
  }

  const bestProducts = state.dashboard.best_products || [];
  const grossRevenue = Number(kpis.gross_revenue ?? kpis.sales_total ?? 0);
  const topRevenue = Math.max(...bestProducts.map((item) => Number(item.revenue || 0)), 1);
  $("#topProducts").innerHTML = bestProducts.length
    ? `<div class="rank-list">${bestProducts
        .map((item, index) => {
          const revenue = Number(item.revenue || 0);
          const share = grossRevenue > 0 ? (revenue / grossRevenue) * 100 : 0;
          const width = Math.max((revenue / topRevenue) * 100, 4);
          return `<article class="rank-item">
            <div class="rank-head">
              <p class="rank-name">${index + 1}. ${escapeHtml(item.name)}</p>
              <p class="rank-value">${formatMoney(revenue)}</p>
            </div>
            <div class="rank-meta">
              <span>Quantidade<b>${item.units} un</b></span>
              <span>Participacao<b>${share.toFixed(1)}%</b></span>
              <span>Lucro produto<b>${formatMoney(item.profit || 0)}</b></span>
            </div>
            <div class="rank-track">
              <div class="rank-bar" style="width:${width}%"></div>
            </div>
          </article>`;
        })
        .join("")}</div>`
    : "<div class='empty-state'>Nenhuma venda registrada no momento.</div>";
}

async function refreshCore() {
  const periodQuery = `?start=${encodeURIComponent(state.dashboardFilter.start)}&end=${encodeURIComponent(
    state.dashboardFilter.end
  )}`;
  const [products, movements, dashboard] = await Promise.all([
    apiOptional("/api/products", []),
    apiOptional("/api/inventory/movements", []),
    apiOptional(`/api/dashboard${periodQuery}`, null),
  ]);
  state.salesEndpointAvailable = true;
  const [sales, financeEntries, suppliers, purchases, costCalculations, categories] = await Promise.all([
    apiOptional("/api/sales", [], () => {
      state.salesEndpointAvailable = false;
    }),
    apiOptional(`/api/finance/entries${periodQuery}`, []),
    apiOptional("/api/suppliers", []),
    apiOptional("/api/purchases", []),
    apiOptional("/api/cost-calculations", []),
    apiOptional("/api/categories", []),
  ]);

  state.products = products;
  state.sales = sales;
  state.movements = movements;
  state.financeEntries = financeEntries;
  state.suppliers = suppliers;
  state.purchases = purchases;
  state.costCalculations = costCalculations;
  state.categories = categories;
  state.dashboard = dashboard;

  if (state.user?.role === "master") {
    state.users = await api("/api/users");
  } else {
    state.users = [];
  }

  renderProductSelects();
  renderCategorySelect();
  renderSupplierSelect();
  renderProducts();
  renderCategories();
  renderSales();
  renderMovements();
  renderStockPosition();
  renderFinance();
  renderUsers();
  renderSuppliers();
  renderPurchases();
  renderCostCalculationHistory();
  renderCostDraft();
  renderDashboard();
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  if (state.authBusy) return;
  state.authBusy = true;
  setLoginSubmitState("loading");
  try {
    const email = $("#loginEmail").value.trim();
    const password = $("#loginPassword").value;
    if (!email || !password) {
      throw new Error("Email e senha são obrigatórios.");
    }
    let data;
    if (state.authMode === "signup") {
      const companyName = $("#signupCompanyName").value.trim();
      const ownerName = $("#signupOwnerName").value.trim();
      if (!companyName) {
        throw new Error("Nome da empresa é obrigatório.");
      }
      if (!ownerName) {
        throw new Error("Nome do administrador é obrigatório.");
      }
      data = await api("/api/signup", "POST", {
        company_name: companyName,
        trade_name: $("#signupTradeName").value.trim(),
        company_email: $("#signupCompanyEmail").value.trim(),
        company_phone: $("#signupCompanyPhone").value.trim(),
        company_document: $("#signupCompanyDocument").value.trim(),
        owner_name: ownerName,
        owner_email: email,
        owner_password: password,
      });
    } else {
      data = await api("/api/login", "POST", { email, password });
    }
    state.token = data.token;
    state.user = data.user;
    localStorage.setItem("token", state.token);

    setLoginSubmitState("success");
    await bootstrapApp();
    setFeedback(state.authMode === "signup" ? "Empresa criada e acesso liberado." : "Acesso realizado com sucesso.");
  } catch (error) {
    setLoginSubmitState("error");
    setFeedback(error.message, true);
    window.setTimeout(() => {
      if (!$("#loginShell").classList.contains("hidden")) {
        setLoginSubmitState("idle");
      }
    }, 1300);
  } finally {
    state.authBusy = false;
  }
}

async function handleCreateProduct(event) {
  event.preventDefault();
  let stopLoading = () => {};
  try {
    const canManage = canAccessModule("products");
    if (!canManage) {
      setFeedback("Seu perfil possui acesso somente para visualizacao.", true);
      return;
    }

    const name = $("#productName").value.trim();
    const costPrice = Number($("#productCost").value || 0);
    const desiredMargin = 30;
    const status = $("#productStatus").value || "active";
    const categoryId = Number($("#productCategory").value || 0);
    const brand = $("#productBrand").value.trim();
    const unit = $("#productUnit").value || "un";
    const description = $("#productDescription").value.trim();
    const barcode = $("#productBarcode").value.trim();

    if (!name) {
      setFeedback("Informe o nome do produto para salvar.", true);
      return;
    }
    if (!Number.isFinite(costPrice) || costPrice < 0) {
      setFeedback("Preco de custo invalido. Informe um valor maior ou igual a zero.", true);
      return;
    }
    if (!Number.isFinite(desiredMargin) || desiredMargin < 0) {
      setFeedback("Margem desejada invalida. Informe percentual maior ou igual a zero.", true);
      return;
    }
    const saveButton = $("#saveProductBtn");
    stopLoading = setButtonLoading(saveButton, true, "Salvando...");

    const payload = {
      sku: $("#sku").value,
      name,
      category_id: categoryId || null,
      brand,
      unit,
      description,
      barcode,
      status,
      cost_price: costPrice,
      desired_margin_percent: desiredMargin,
      cost_items: [],
    };

    if (state.editingProductId) {
      await api(`/api/products/${state.editingProductId}`, "PUT", payload);
      setFeedback("Produto atualizado com sucesso.");
    } else {
      await api("/api/products", "POST", payload);
      setFeedback("Produto criado com sucesso. Estoque inicia em zero.");
    }

    resetProductFormMode();
    await refreshCore();
    stopLoading();
  } catch (error) {
    setFeedback(error.message, true);
  } finally {
    stopLoading();
  }
}

async function submitInventory(type) {
  const isEntry = type === "entry";
  const queryInput = $(isEntry ? "#entryProductQuery" : "#exitProductQuery");
  const selectInput = $(isEntry ? "#entryProduct" : "#exitProduct");
  const resolvedByQuery = resolveProductByLookupQuery(queryInput?.value || "", { activeOnly: true });
  if (resolvedByQuery) {
    selectInput.value = String(resolvedByQuery.id);
  }
  const productId = Number(selectInput.value);
  const qty = parsePositiveInteger($(isEntry ? "#entryQty" : "#exitQty").value, "Quantidade");
  const note = $(isEntry ? "#entryNote" : "#exitNote").value;
  const createdAt = $(isEntry ? "#entryDateTime" : "#exitDateTime").value;
  if (!productId) {
    throw new Error("Selecione ou busque um produto válido para registrar a movimentação.");
  }
  if (!createdAt) {
    throw new Error("Informe data e hora da movimentacao.");
  }

  await api(`/api/inventory/${type}`, "POST", {
    product_id: productId,
    qty,
    note,
    created_at: createdAt,
  });

  await refreshCore();
  $(isEntry ? "#entryQty" : "#exitQty").value = "1";
  $(isEntry ? "#entryNote" : "#exitNote").value = "";
  if (queryInput) queryInput.value = "";
  $(isEntry ? "#entryDateTime" : "#exitDateTime").value = toDateTimeLocalValue();
  const updated = state.products.find((p) => Number(p.id) === productId);
  const currentQty = Number(updated?.stock_qty || 0);
  if (!isEntry && currentQty <= 0) {
    setFeedback("Saída registrada. Atenção: produto ficou com estoque zerado.");
    return;
  }
  if (!isEntry && currentQty <= 5) {
    setFeedback(`Saída registrada. Atenção: estoque baixo (${currentQty} un).`);
    return;
  }
  setFeedback(isEntry ? "Entrada de estoque registrada." : "Saida de estoque registrada.");
}

async function handleSale(event) {
  event.preventDefault();
  try {
    const saleQueryInput = $("#saleProductQuery");
    const saleSelect = $("#saleProduct");
    const resolvedByQuery = resolveProductByLookupQuery(saleQueryInput?.value || "", { activeOnly: true });
    if (resolvedByQuery) {
      saleSelect.value = String(resolvedByQuery.id);
      saleQueryInput.value = resolvedByQuery.name || saleQueryInput.value;
    }
    const productId = Number(saleSelect.value);
    const qty = parsePositiveInteger($("#saleQty").value, "Quantidade da venda");
    const unitPrice = Number($("#salePrice").value);
    const createdAt = $("#saleDateTime").value;
    if (!productId) {
      throw new Error("Selecione um produto para registrar a venda.");
    }
    if (!Number.isFinite(unitPrice) || unitPrice <= 0) {
      throw new Error("Preco unitario deve ser maior que zero.");
    }
    if (!createdAt) {
      throw new Error("Informe data e hora da venda.");
    }

    const isEditing = Boolean(state.editingSaleId);
    const payload = {
      product_id: productId,
      qty,
      unit_price: unitPrice,
      created_at: createdAt,
    };
    const result = isEditing
      ? await api(`/api/sales/${state.editingSaleId}`, "PUT", payload)
      : await api("/api/sales", "POST", payload);

    await refreshCore();
    const updated = state.products.find((p) => Number(p.id) === productId);
    const currentQty = Number(updated?.stock_qty || 0);
    resetSaleFormMode();
    if (currentQty <= 0) {
      setFeedback(`Venda ${isEditing ? "atualizada" : "registrada"}. Estoque zerado para este item.`);
      return;
    }
    if (currentQty <= 5) {
      setFeedback(`Venda ${isEditing ? "atualizada" : "registrada"}. Estoque baixo (${currentQty} un).`);
      return;
    }
    setFeedback(
      isEditing
        ? `Venda atualizada. Total: ${formatMoney(result.total)}`
        : `Venda registrada. Total: ${formatMoney(result.total)}`
    );
  } catch (error) {
    setFeedback(error.message, true);
  }
}

async function handleFinance(type, event) {
  event.preventDefault();
  try {
    const isExpense = type === "expense";
    const category = $(isExpense ? "#expenseCategory" : "#incomeCategory").value.trim();
    const description = $(isExpense ? "#expenseDescription" : "#incomeDescription").value.trim();
    const amount = Number($(isExpense ? "#expenseAmount" : "#incomeAmount").value);
    const createdAt = $(isExpense ? "#expenseDateTime" : "#incomeDateTime").value;
    const paymentMethod = $(isExpense ? "#expensePaymentMethod" : "#incomePaymentMethod").value.trim();
    const paymentTerms = $(isExpense ? "#expensePaymentTerms" : "#incomePaymentTerms").value.trim();
    const paymentStatus = $(isExpense ? "#expensePaymentStatus" : "#incomePaymentStatus").value;
    const notes = $(isExpense ? "#expenseNotes" : "#incomeNotes").value.trim();
    if (!category) {
      throw new Error("Informe a categoria do lancamento.");
    }
    if (!Number.isFinite(amount) || amount <= 0) {
      throw new Error("Valor deve ser maior que zero.");
    }
    if (!createdAt) {
      throw new Error("Informe data e hora do lancamento.");
    }

    await api(`/api/finance/${type}`, "POST", {
      category,
      description,
      amount,
      created_at: createdAt,
      payment_method: paymentMethod,
      payment_terms: paymentTerms,
      payment_status: paymentStatus,
      notes,
    });

    event.target.reset();
    if (isExpense) {
      $("#expenseCategory").value = "Operacional";
      $("#expenseDateTime").value = toDateTimeLocalValue();
      $("#expensePaymentMethod").value = "PIX";
      $("#expensePaymentTerms").value = "À vista";
      $("#expensePaymentStatus").value = "pago";
    } else {
      $("#incomeCategory").value = "Receita extra";
      $("#incomeDateTime").value = toDateTimeLocalValue();
      $("#incomePaymentMethod").value = "PIX";
      $("#incomePaymentTerms").value = "À vista";
      $("#incomePaymentStatus").value = "pago";
    }

    await refreshCore();
    setFeedback(isExpense ? "Gasto registrado com sucesso." : "Ganho registrado com sucesso.");
  } catch (error) {
    setFeedback(error.message, true);
  }
}

async function handleUserSave(event) {
  event.preventDefault();
  let stopLoading = () => {};
  try {
    const name = $("#newUserName").value.trim();
    const email = $("#newUserEmail").value.trim();
    const password = $("#newUserPassword").value.trim();
    const role = $("#newUserRole").value;
    const modulePermissions = selectedUserPermissionsFromForm();
    const avatarUrl = state.userAvatarDraft || null;

    if (!name) {
      throw new Error("Informe o nome do usuário.");
    }
    if (!state.editingUserId && !email.includes("@")) {
      throw new Error("Informe um e-mail válido para criar o usuário.");
    }
    if (state.editingUserId && password && password.length < 4) {
      throw new Error("Senha deve ter pelo menos 4 caracteres.");
    }

    if (state.editingUserId) {
      stopLoading = setButtonLoading($("#saveUserBtn"), true, "Salvando...");
      await api(`/api/users/${state.editingUserId}`, "PUT", {
        name,
        role,
        module_permissions: modulePermissions,
        avatar_url: avatarUrl,
      });
      if (password) {
        await api(`/api/users/${state.editingUserId}/reset-password`, "PUT", { new_password: password });
      }
      if (Number(state.user?.id) === Number(state.editingUserId)) {
        state.user = await api("/api/me");
        updateSidebarIdentity();
      }
      setFeedback("Usuário atualizado com sucesso.");
    } else {
      if (!password || password.length < 4) {
        throw new Error("Senha deve ter pelo menos 4 caracteres.");
      }
      stopLoading = setButtonLoading($("#saveUserBtn"), true, "Criando...");
      await api("/api/users", "POST", {
        name,
        email,
        password,
        role,
        module_permissions: modulePermissions,
        avatar_url: avatarUrl,
      });
      setFeedback("Usuário criado com sucesso.");
    }

    resetUserFormMode();
    state.users = await api("/api/users");
    renderUsers();
  } catch (error) {
    setFeedback(error.message, true);
  } finally {
    stopLoading();
  }
}

async function handleSaveCostProfile() {
  let stopLoading = () => {};
  try {
    const calc = state.currentCostCalc || {};
    if (!Number.isFinite(calc.sale_price) || calc.sale_price <= 0) {
      throw new Error("Preencha a calculadora com valores válidos antes de salvar.");
    }
    const productId = Number($("#costCalcProduct").value || 0);
    const product = state.products.find((p) => Number(p.id) === productId);
    stopLoading = setButtonLoading($("#saveCostCalcBtn"), true, "Salvando...");
    await api("/api/cost-calculations", "POST", {
      product_id: productId || null,
      product_name: product?.name || "Simulação avulsa",
      ...calc,
    });
    await refreshCore();
    setFeedback("Cálculo salvo com sucesso.");
  } catch (error) {
    setFeedback(error.message, true);
  } finally {
    stopLoading();
  }
}

async function handleSupplierSave(event) {
  event.preventDefault();
  let stopLoading = () => {};
  try {
    const name = $("#supplierName").value.trim();
    if (!name) throw new Error("Nome do fornecedor é obrigatório.");
    stopLoading = setButtonLoading(event.submitter, true, "Salvando...");
    const editingId = Number($("#supplierForm").dataset.editingSupplierId || 0);
    const payload = {
      name,
      contact: $("#supplierContact").value.trim(),
      phone: $("#supplierPhone").value.trim(),
      email: $("#supplierEmail").value.trim(),
      notes: $("#supplierNotes").value.trim(),
      is_active: $("#supplierStatus").value === "active",
    };
    if (editingId) {
      await api(`/api/suppliers/${editingId}`, "PUT", payload);
      setFeedback("Fornecedor atualizado com sucesso.");
    } else {
      await api("/api/suppliers", "POST", payload);
      setFeedback("Fornecedor criado com sucesso.");
    }
    $("#supplierForm").reset();
    $("#supplierStatus").value = "active";
    delete $("#supplierForm").dataset.editingSupplierId;
    await refreshCore();
  } catch (error) {
    setFeedback(error.message, true);
  } finally {
    stopLoading();
  }
}

async function handleCategorySave(event) {
  event.preventDefault();
  let stopLoading = () => {};
  try {
    const name = $("#categoryName").value.trim();
    if (!name) throw new Error("Informe o nome da categoria.");
    const payload = {
      name,
      description: $("#categoryDescription").value.trim(),
      status: $("#categoryStatus").value || "active",
    };
    stopLoading = setButtonLoading($("#saveCategoryBtn"), true, state.editingCategoryId ? "Salvando..." : "Criando...");
    if (state.editingCategoryId) {
      await api(`/api/categories/${state.editingCategoryId}`, "PUT", payload);
      setFeedback("Categoria atualizada com sucesso.");
    } else {
      await api("/api/categories", "POST", payload);
      setFeedback("Categoria criada com sucesso.");
    }
    resetCategoryFormMode();
    await refreshCore();
  } catch (error) {
    setFeedback(error.message, true);
  } finally {
    stopLoading();
  }
}

async function handlePurchaseSave(event) {
  event.preventDefault();
  let stopLoading = () => {};
  try {
    const purchaseType = $("#purchaseType").value;
    const qty = parsePositiveInteger($("#purchaseQty").value || 0, "Quantidade da compra");
    const unitCost = Number($("#purchaseUnitCost").value || 0);
    const createdAt = $("#purchaseDateTime").value;
    if (!createdAt) throw new Error("Informe data e hora da compra.");
    if (!Number.isFinite(unitCost) || unitCost < 0) throw new Error("Custo unitário inválido.");
    const productId = Number($("#purchaseProduct").value || 0);
    const itemLabel = $("#purchaseItemLabel").value.trim();
    if (!productId && !itemLabel) throw new Error("Selecione um produto ou informe descrição do item.");

    const isEditing = Boolean(state.editingPurchaseId);
    stopLoading = setButtonLoading($("#savePurchaseBtn"), true, isEditing ? "Salvando..." : "Registrando...");
    const payload = {
      supplier_id: Number($("#purchaseSupplier").value || 0) || null,
      purchase_type: purchaseType,
      payment_method: $("#purchasePaymentMethod").value.trim() || "N/A",
      payment_terms: $("#purchasePaymentTerms").value.trim() || "À vista",
      payment_status: $("#purchasePaymentStatus").value,
      notes: $("#purchaseNotes").value.trim(),
      created_at: createdAt,
      items: [
        {
          product_id: productId || null,
          label: itemLabel || (state.products.find((p) => Number(p.id) === productId)?.name || "Item da compra"),
          qty,
          unit_cost: unitCost,
          total_cost: Number((qty * unitCost).toFixed(2)),
          affects_stock: purchaseType === "inventory" && Boolean(productId),
        },
      ],
    };
    if (isEditing) {
      await api(`/api/purchases/${state.editingPurchaseId}`, "PUT", payload);
    } else {
      await api("/api/purchases", "POST", payload);
    }
    resetPurchaseFormMode();
    await refreshCore();
    setFeedback(isEditing ? "Compra atualizada com sucesso." : "Compra registrada com sucesso.");
  } catch (error) {
    setFeedback(error.message, true);
  } finally {
    stopLoading();
  }
}

function bindEvents() {
  $("#landingLoginBtn")?.addEventListener("click", () => openAuthShell("login"));
  $("#landingSignupBtn")?.addEventListener("click", () => openAuthShell("signup"));
  $("#landingCtaLoginBtn")?.addEventListener("click", () => openAuthShell("login"));
  $("#landingCtaSignupBtn")?.addEventListener("click", () => openAuthShell("signup"));

  $("#loginForm").addEventListener("submit", handleAuthSubmit);
  $("#authModeLogin")?.addEventListener("click", () => setAuthMode("login"));
  $("#authModeSignup")?.addEventListener("click", () => setAuthMode("signup"));
  setAuthMode("login");
  setDashboardRange("30d");
  setOperationDateDefaults();

  const financeCanvas = $("#financeChart");
  if (financeCanvas) {
    financeCanvas.addEventListener("mousemove", (event) => {
      const model = state.financeChartModel;
      if (!model || !model.points?.length) {
        hideFinanceTooltip();
        return;
      }

      const rect = financeCanvas.getBoundingClientRect();
      const localX = event.clientX - rect.left;
      const localY = event.clientY - rect.top;
      let hoveredIndex = model.points.findIndex((point) => localX >= point.left && localX <= point.right);

      if (hoveredIndex === -1) {
        let nearestDistance = Number.POSITIVE_INFINITY;
        model.points.forEach((point, idx) => {
          const distance = Math.abs(point.centerX - localX);
          if (distance < nearestDistance) {
            nearestDistance = distance;
            hoveredIndex = idx;
          }
        });
      }

      if (hoveredIndex !== state.financeHoverIndex) {
        state.financeHoverIndex = hoveredIndex;
        drawFinanceChart(state.dashboard?.monthly || []);
      }
      showFinanceTooltip(hoveredIndex, localX, localY);
    });

    financeCanvas.addEventListener("mouseleave", () => {
      if (state.financeHoverIndex !== -1) {
        state.financeHoverIndex = -1;
        drawFinanceChart(state.dashboard?.monthly || []);
      }
      hideFinanceTooltip();
    });
  }

  const togglePasswordBtn = $("#togglePasswordBtn");
  if (togglePasswordBtn) {
    togglePasswordBtn.addEventListener("click", () => {
      const passwordInput = $("#loginPassword");
      const eye = togglePasswordBtn.querySelector(".icon-eye");
      const eyeOff = togglePasswordBtn.querySelector(".icon-eye-off");
      const show = passwordInput.type === "password";
      passwordInput.type = show ? "text" : "password";
      togglePasswordBtn.setAttribute("aria-label", show ? "Ocultar senha" : "Mostrar senha");
      eye.classList.toggle("hidden", show);
      eyeOff.classList.toggle("hidden", !show);
    });
  }

  $$(".nav-item[data-section]").forEach((btn) => {
    btn.addEventListener("click", () => applySection(btn.dataset.section));
  });

  $("#logoutBtn").addEventListener("click", () => {
    localStorage.removeItem("token");
    state.token = "";
    state.user = null;
    showLandingShell();
    setLoginSubmitState("idle");
    setFeedback("Sessao finalizada.");
  });

  $("#applyDateFilterBtn").addEventListener("click", async () => {
    try {
      setDashboardCustomRangeFromInputs();
      await refreshCore();
      if (state.activeSection === "dashboard" || state.activeSection === "financeiro") {
        applySection(state.activeSection);
      }
      setFeedback("Periodo atualizado para dashboard e financeiro.");
    } catch (error) {
      setFeedback(error.message, true);
    }
  });

  $$(".range-chip").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        setDashboardRange(btn.dataset.range);
        await refreshCore();
        if (state.activeSection === "dashboard" || state.activeSection === "financeiro") {
          applySection(state.activeSection);
        }
        setFeedback("Filtro rapido aplicado.");
      } catch (error) {
        setFeedback(error.message, true);
      }
    });
  });

  $("#sidebarToggle").addEventListener("click", () => {
    if (isMobileViewport()) {
      $("#appShell").classList.toggle("menu-open");
      return;
    }

    state.sidebarCollapsed = !state.sidebarCollapsed;
    localStorage.setItem("sidebarCollapsed", state.sidebarCollapsed ? "1" : "0");
    applySidebarState();
  });

  ["#calcCost", "#calcShipping", "#calcOtherCosts", "#calcTaxPercent", "#calcCommissionPercent", "#calcMarginPercent"].forEach(
    (selector) => {
      const el = $(selector);
      if (el) el.addEventListener("input", renderCostDraft);
    }
  );

  $("#productForm").addEventListener("submit", handleCreateProduct);
  const saveCostCalcBtn = $("#saveCostCalcBtn");
  if (saveCostCalcBtn) {
    saveCostCalcBtn.addEventListener("click", handleSaveCostProfile);
  }
  const clearCostCalcBtn = $("#clearCostCalcBtn");
  if (clearCostCalcBtn) {
    clearCostCalcBtn.addEventListener("click", () => {
      $("#costCalculatorForm").reset();
      $("#calcMarginPercent").value = "30";
      renderCostDraft();
    });
  }
  const costCalcProduct = $("#costCalcProduct");
  if (costCalcProduct) {
    costCalcProduct.addEventListener("change", (event) => {
      const productId = Number(event.target.value || 0);
      if (productId) {
        loadCostProfileFromProduct(productId);
      } else {
        renderCostDraft();
      }
    });
  }
  $("#cancelEditBtn").addEventListener("click", () => {
    resetProductFormMode();
    setFeedback("Edicao cancelada.");
  });

  $("#stockEntryForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await submitInventory("entry");
    } catch (error) {
      setFeedback(error.message, true);
    }
  });

  $("#stockExitForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await submitInventory("exit");
    } catch (error) {
      setFeedback(error.message, true);
    }
  });

  $("#saleForm").addEventListener("submit", handleSale);
  $("#cancelSaleEditBtn").addEventListener("click", () => {
    resetSaleFormMode();
    setFeedback("Edicao de venda cancelada.");
  });
  $("#expenseForm").addEventListener("submit", (event) => handleFinance("expense", event));
  $("#incomeForm").addEventListener("submit", (event) => handleFinance("income", event));
  $("#userForm").addEventListener("submit", handleUserSave);
  $("#cancelUserEditBtn").addEventListener("click", () => {
    resetUserFormMode();
    setFeedback("Edicao de usuario cancelada.");
  });
  $("#newUserName").addEventListener("input", () => {
    renderUserAvatarPreview($("#newUserName").value || "Usuário");
  });
  $("#newUserAvatarFile").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      if (!String(file.type || "").startsWith("image/")) {
        throw new Error("Selecione um arquivo de imagem válido.");
      }
      if (Number(file.size || 0) > 700 * 1024) {
        throw new Error("A imagem é muito grande. Use até 700KB.");
      }
      state.userAvatarDraft = await readFileAsDataUrl(file);
      renderUserAvatarPreview($("#newUserName").value || "Usuário");
      setFeedback("Foto carregada. Clique em salvar para aplicar.");
    } catch (error) {
      event.target.value = "";
      setFeedback(error.message, true);
    }
  });
  $("#removeUserAvatarBtn").addEventListener("click", () => {
    state.userAvatarDraft = null;
    $("#newUserAvatarFile").value = "";
    renderUserAvatarPreview($("#newUserName").value || "Usuário");
    setFeedback("Foto removida. Salve para confirmar.");
  });
  $("#newUserRole").addEventListener("change", () => {
    if (!state.editingUserId) {
      applyRolePresetToPermissionForm($("#newUserRole").value);
    }
  });
  $("#permSelectAllBtn").addEventListener("click", () => {
    setUserPermissionsForm(["dashboard", "products", "costs", "purchases", "inventory", "sales", "finance", "users"]);
  });
  $("#permClearAllBtn").addEventListener("click", () => {
    setUserPermissionsForm([]);
  });
  $("#permissionPreset").addEventListener("change", (event) => {
    const value = event.target.value;
    if (!value) return;
    applyPermissionPreset(value);
  });
  $("#supplierForm").addEventListener("submit", handleSupplierSave);
  $("#supplierSearch").addEventListener("input", renderSuppliers);
  $("#deleteSelectedSuppliersBtn").addEventListener("click", deleteSelectedSuppliers);
  $("#deactivateSelectedSuppliersBtn").addEventListener("click", () => updateSupplierStatusBulk(false));
  $("#reactivateSelectedSuppliersBtn").addEventListener("click", () => updateSupplierStatusBulk(true));
  $("#purchaseForm").addEventListener("submit", handlePurchaseSave);
  $("#purchaseSearch").addEventListener("input", renderPurchases);
  $("#deleteSelectedPurchasesBtn").addEventListener("click", deleteSelectedPurchases);
  $("#cancelPurchaseEditBtn").addEventListener("click", () => {
    resetPurchaseFormMode();
    setFeedback("Edicao de compra cancelada.");
  });
  $("#purchaseType").addEventListener("change", () => {
    const isInventory = $("#purchaseType").value === "inventory";
    const purchaseProduct = $("#purchaseProduct");
    purchaseProduct.disabled = !isInventory;
    if (!isInventory) {
      purchaseProduct.value = "";
    }
  });
  $("#categoryForm").addEventListener("submit", handleCategorySave);
  $("#cancelCategoryEditBtn").addEventListener("click", () => {
    resetCategoryFormMode();
    setFeedback("Edicao de categoria cancelada.");
  });
  $("#categorySearch").addEventListener("input", renderCategories);
  $("#deleteSelectedCategoriesBtn").addEventListener("click", deleteSelectedCategories);
  $("#deactivateSelectedCategoriesBtn").addEventListener("click", () => updateCategoryStatusBulk("inactive"));
  $("#reactivateSelectedCategoriesBtn").addEventListener("click", () => updateCategoryStatusBulk("active"));
  $("#stockPositionSearch").addEventListener("input", renderStockPosition);

  ["entry", "exit"].forEach((mode) => {
    const queryInput = $(`#${mode}ProductQuery`);
    const select = $(`#${mode}Product`);
    if (queryInput && select) {
      queryInput.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        const resolved = resolveProductByLookupQuery(queryInput.value || "", { activeOnly: true });
        if (resolved) {
          select.value = String(resolved.id);
          queryInput.value = resolved.name || queryInput.value;
        }
      });
      queryInput.addEventListener("blur", () => {
        const resolved = resolveProductByLookupQuery(queryInput.value || "", { activeOnly: true });
        if (resolved) {
          select.value = String(resolved.id);
          queryInput.value = resolved.name || queryInput.value;
        }
      });
      select.addEventListener("change", () => {
        const selected = state.products.find((p) => Number(p.id) === Number(select.value));
        if (selected) {
          queryInput.value = selected.name || "";
        }
      });
    }
  });
  const saleQueryInput = $("#saleProductQuery");
  const saleSelect = $("#saleProduct");
  if (saleQueryInput && saleSelect) {
    saleQueryInput.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      const resolved = resolveProductByLookupQuery(saleQueryInput.value || "", { activeOnly: true });
      if (resolved) {
        saleSelect.value = String(resolved.id);
        saleQueryInput.value = resolved.name || saleQueryInput.value;
      }
    });
    saleQueryInput.addEventListener("blur", () => {
      const resolved = resolveProductByLookupQuery(saleQueryInput.value || "", { activeOnly: true });
      if (resolved) {
        saleSelect.value = String(resolved.id);
        saleQueryInput.value = resolved.name || saleQueryInput.value;
      }
    });
    saleSelect.addEventListener("change", () => {
      const selected = state.products.find((p) => Number(p.id) === Number(saleSelect.value));
      if (selected) {
        saleQueryInput.value = selected.name || "";
      }
    });
  }

  $("#productSearch").addEventListener("input", renderProducts);
  $("#productStatusFilter").addEventListener("change", renderProducts);
  $("#movementSearch").addEventListener("input", renderMovements);
  $("#deleteSelectedProductsBtn").addEventListener("click", deleteSelectedProducts);
  $("#deactivateSelectedProductsBtn").addEventListener("click", deactivateSelectedProducts);
  $("#deleteSelectedMovementsBtn").addEventListener("click", deleteSelectedMovements);
  $("#salesSearch").addEventListener("input", renderSales);
  $("#deleteSelectedSalesBtn").addEventListener("click", deleteSelectedSales);
  $("#financeSearch").addEventListener("input", renderFinance);
  $("#deleteSelectedFinanceBtn").addEventListener("click", deleteSelectedFinanceEntries);
  $("#usersSearch").addEventListener("input", renderUsers);
  $("#userStatusFilter").addEventListener("change", renderUsers);
  $("#deactivateSelectedUsersBtn").addEventListener("click", deactivateSelectedUsers);
  $("#reactivateSelectedUsersBtn").addEventListener("click", reactivateSelectedUsers);
  $("#deleteSelectedUsersBtn").addEventListener("click", deleteSelectedUsers);
  window.addEventListener("resize", () => {
    applySidebarState();
    if (!isMobileViewport()) {
      $("#appShell").classList.remove("menu-open");
    }
    if (state.dashboard) {
      drawFinanceChart(state.dashboard.monthly || []);
    }
  });

  applySidebarState();
}

async function bootstrapApp() {
  showAppShell();
  applySidebarState();
  state.selectedProductIds.clear();
  state.selectedCategoryIds.clear();
  state.selectedSaleIds.clear();
  state.selectedMovementIds.clear();
  state.selectedFinanceIds.clear();
  state.selectedUserIds.clear();
  state.selectedSupplierIds.clear();
  state.selectedPurchaseIds.clear();
  resetProductFormMode();
  resetCategoryFormMode();
  resetSaleFormMode();
  resetPurchaseFormMode();
  resetUserFormMode();
  renderCostDraft();
  updateSidebarIdentity();
  applyProductsPermissions();
  applyNavigationPermissions();

  await refreshCore();
  const initialSection = allowedSections()[0] || "dashboard";
  applySection(initialSection);
}

async function init() {
  bindEvents();
  if (!state.token) {
    showLandingShell();
    return;
  }

  try {
    state.user = await api("/api/me");
    await bootstrapApp();
  } catch {
    localStorage.removeItem("token");
    state.token = "";
    showLandingShell();
  }
}

init();
