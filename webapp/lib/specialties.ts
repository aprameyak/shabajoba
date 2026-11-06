// EE specialties a role can be filed under; a role can match several.
const RULES: [string, RegExp][] = [
  ['Electrical Engineering', /electrical|\bee\b|\bece\b/i],
  ['Hardware Engineering', /hardware|\bhw\b/i],
  ['Electrical Test Engineering', /\btest|electromagnetic compatibility|\bemc\b|\bemi\b/i],
  ['Electronics Engineering', /electronic|electro-?optic|avionic|mechatronic|\becu\b|\bcomponent/i],
  ['Embedded Systems', /embedded/i],
  ['Firmware Engineering', /firmware/i],
  ['Systems Engineering', /\bsystems?\b|\bsys\b|integration/i],
  ['Hardware Validation Engineering', /validation|verification|characteri[sz]ation|bring.?up|\bdv\b/i],
  ['Power Systems Engineering', /power systems?|\bgrid\b|substation|transmission|protection|utility|utilities|energy|nuclear|fusion|gas & electric/i],
  ['Power Electronics Engineering', /power electronic|power conversion|power delivery|inverter|converter|motor drive|charg(?:er|ing)|battery|power supply|power management|\bpmic\b/i],
  ['Manufacturing Engineering', /manufactur|production|assembly|\bnpi\b|process eng|equipment eng|yield|quality|reliability/i],
  ['Product Engineering', /product eng|product development|product test/i],
  ['PCB Design Engineering', /\bpcb|board design|\blayout|harness|schematic/i],
  ['RF Engineering', /\brf|rfic|microwave|antenna|mm-?wave|radar/i],
  ['FPGA Engineering', /fpga/i],
  ['Digital Design Engineering', /digital design|digital ic|\brtl\b|logic design|synthesis|\bhls\b/i],
  ['ASIC / VLSI Design', /asic|vlsi|physical design|\bsoc\b|\bic design|silicon|analog|mixed.?signal|circuit design|\bchip|sram|dram|\bhbm\b|\btiming\b/i],
  ['Semiconductor Engineering', /semiconductor|wafer|\bfab\b|lithograph|\betch|metrology|process integration|\bdevice|failure analysis|packaging|thin film|cmos|photonic|\bpic\b/i],
  ['Controls Engineering', /control|calibration/i],
  ['Robotics Engineering', /robot|autonom/i],
  ['Signal Processing Engineering', /signal|\bdsp\b|audio|acoustic|imaging|sonar|lidar/i],
  ['Communications Engineering', /communication|telecom|wireless|network|\b5g\b|wi-?fi|satcom|optical|serdes/i],
  ['Automation Engineering', /automation|\bplc\b|scada/i],
  ['Electrical Design Engineering', /electrical design|electrical designer|design engineer/i],
  ['Field Applications Engineering', /\bfield\b|applications? eng|\bfae\b/i],
];

export const SPECIALTIES = RULES.map(([name]) => name);

export function specialtiesFor(role: string): string[] {
  const found = RULES.filter(([, re]) => re.test(role)).map(([name]) => name);
  return found.length ? found : ['Electrical Engineering'];
}
